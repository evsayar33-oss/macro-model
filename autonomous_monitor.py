"""
Autonomous Macro Regime Monitor (runs from .github/workflows/auto_run.yml)
===========================================================================
Previously this code lived inline inside the workflow YAML. It is now a
normal Python file so it can be read, tested and shared with the Streamlit
app and the historical validator.

v2.4 additions (behaviour otherwise unchanged):
* Computes the same 8-asset signal scan as the app (asset_signal_engine) and
  persists it (`asset_signals`).
* Target portfolio weights now use those signal scores, exactly like the app.
  Before, the automation called compute_target_portfolio_weights() WITHOUT
  signals, so the persisted portfolio differed from the one the UI showed.
"""
import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone

import requests

import numpy as np
import pandas as pd
import yfinance as yf

from macro_event_interpretation import (
    MACRO_EVENT_INPUT_SCHEMA_VERSION,
    MACRO_INPUT_KEYS,
    CRITICAL_INPUT_KEYS,
    REGIME_NAMES,
    CONTINUUM_REGIME_MAP,
    MacroEventInterpretationSystem,
    compute_continuum_regime_state,
    compute_circuit_breaker,
    compute_structural_risk_state,
    compute_portfolio_asset_tilt,
    compute_target_portfolio_weights,
    compute_effective_macro_asset_multiplier,
    compute_net_liquidity,
    assess_data_freshness,
    get_macro_interpretation_asset_multipliers,
    normalize_macro_input,
    validate_macro_input,
)
from asset_regime_weights import (
    ASSETS,
    INDICATORS,
    get_dynamic_asset_weights,
)

REPO_DIR = os.getcwd()
SUMMARY_PATH = os.path.join(REPO_DIR, "backtest_summary.json")

def clean_series(s: pd.Series) -> pd.Series:
    s = pd.Series(s).copy()
    s.index = pd.to_datetime(s.index, errors="coerce")
    s = s[~s.index.isna()]
    s = pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan)
    s = s.dropna().sort_index()
    if s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    return s.astype(float)

def fetch_fred(series_id: str) -> pd.Series:
    url = (
        "https://fred.stlouisfed.org/graph/fredgraph.csv"
        f"?id={series_id}&cosd=2014-01-01"
    )
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=25)
            response.raise_for_status()
            if not response.text.strip():
                raise ValueError("empty FRED response")
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))
            if df.empty:
                raise ValueError("empty FRED dataframe")
            date_col = next(
                (c for c in df.columns if c.lower() in {"date", "observation_date"}),
                df.columns[0],
            )
            value_cols = [c for c in df.columns if c != date_col]
            if not value_cols:
                raise ValueError("no FRED value column")
            value_col = value_cols[0]
            idx = pd.to_datetime(df[date_col], errors="coerce")
            vals = pd.to_numeric(df[value_col].replace(".", np.nan), errors="coerce")
            return clean_series(pd.Series(vals.values, index=idx))
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    print(f"[ERROR] FRED {series_id} failed after retries: {last_error}")
    return pd.Series(dtype=float)

def fetch_yf(ticker: str) -> pd.Series:
    last_error = None
    for attempt in range(3):
        try:
            data = yf.download(
                ticker,
                period="20y",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
                timeout=25,
            )
            if data.empty:
                raise ValueError("empty Yahoo dataframe")
            if isinstance(data.columns, pd.MultiIndex):
                if "Close" in data.columns.get_level_values(0):
                    s = data["Close"]
                else:
                    s = data.iloc[:, 0]
            elif "Close" in data.columns:
                s = data["Close"]
            else:
                s = data.iloc[:, 0]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            result = clean_series(s)
            if result.empty:
                raise ValueError("Yahoo returned no usable close values")
            return result
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    print(f"[ERROR] Yahoo {ticker} failed after retries: {last_error}")
    return pd.Series(dtype=float)

def compute_global_net_liquidity(walcl, tga, rrp) -> pd.Series:
    return compute_net_liquidity(walcl, tga, rrp)

def data_fingerprint(normalized_input: dict) -> str:
    latest = {}
    for key in MACRO_INPUT_KEYS:
        series = normalized_input.get(key, pd.Series(dtype=float))
        if series.empty:
            latest[key] = None
        else:
            latest[key] = {
                "date": pd.Timestamp(series.index[-1]).isoformat(),
                "value": round(float(series.iloc[-1]), 10),
            }
    payload = json.dumps(latest, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def json_safe(obj):
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        value = float(obj)
        return value if math.isfinite(value) else None
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    return obj

# 1) Fresh macro data collection
fred_ids = {
    "ust2y": "DGS2", "ust10y": "DGS10", "dfii10": "DFII10",
    "t10yie": "T10YIE", "t5yifr": "T5YIFR", "hy_oas": "BAMLH0A0HYM2",
    "ig_oas": "BAMLC0A0CM", "nfci": "NFCI", "icsa": "ICSA",
    "dtwex": "DTWEXBGS", "walcl": "WALCL", "tga": "WTREGEN", "rrp": "RRPONTSYD",
    # factor-signal inputs (same series the Streamlit app uses)
    "effr": "EFFR", "t10y2y": "T10Y2Y", "wresbal": "WRESBAL",
    "ecb": "ECBASSETSW", "boj": "JPNASSETS",
}
fred_data = {key: fetch_fred(value) for key, value in fred_ids.items()}

yf_ids = {
    "oil": "CL=F", "bdi": "BDRY", "dxy": "DX-Y.NYB", "usdjpy": "JPY=X",
    "vix": "^VIX", "move": "^MOVE", "btc": "BTC-USD", "spx": "SPY",
    "gold": "GC=F", "xag": "SI=F", "hg": "HG=F", "dbb": "DBB", "eurusd": "EURUSD=X",
    "bank_equity": "XLF", "small_caps": "IWM",
    "qqq": "QQQ", "tlt": "TLT",
}
yf_data = {key: fetch_yf(value) for key, value in yf_ids.items()}

# Keep source semantics identical to the Streamlit application:
# DTWEX may fall back to DXY, while the canonical DXY field itself
# remains the direct DXY series and is allowed to be empty.
dxy = yf_data["dxy"]
dtwex = fred_data["dtwex"] if not fred_data["dtwex"].empty else yf_data["dxy"]
ndl = compute_global_net_liquidity(fred_data["walcl"], fred_data["tga"], fred_data["rrp"])

# 2) Canonical shared event-input contract. The module is the single
# source of truth for field names; this workflow only maps fresh data
# into those canonical fields.
macro_input = {
    "oil": yf_data["oil"], "bdi": yf_data["bdi"], "hy_oas": fred_data["hy_oas"],
    "ig_oas": fred_data["ig_oas"], "spx": yf_data["spx"], "ust10y": fred_data["ust10y"],
    "ust2y": fred_data["ust2y"], "dtwex": dtwex, "dxy": dxy,
    "usdjpy": yf_data["usdjpy"], "vix": yf_data["vix"], "move": yf_data["move"],
    "btc": yf_data["btc"], "dfii10": fred_data["dfii10"], "t10yie": fred_data["t10yie"],
    "ndl": ndl, "gold": yf_data["gold"], "xag": yf_data["xag"], "hg": yf_data["hg"],
    "dbb": yf_data["dbb"], "nfci": fred_data["nfci"], "icsa": fred_data["icsa"],
    "bank_equity": yf_data["bank_equity"], "small_caps": yf_data["small_caps"],
}

contract_report = validate_macro_input(macro_input, require_critical=False)
if contract_report["unknown_keys"] or contract_report["missing_keys"]:
    raise RuntimeError("Macro input contract mismatch: " + contract_report["message"])

normalized_input = normalize_macro_input(macro_input, strict=True)
freshness = assess_data_freshness(normalized_input)
missing = list(contract_report["critical_missing_keys"])
stale_critical = [k for k in CRITICAL_INPUT_KEYS if k in freshness["stale_keys"]]
if len(missing) + len(stale_critical) >= 3:
    raise RuntimeError(
        "Güvenilir rejim hesaplaması durduruldu; kritik veri eksikleri/eski veriler: "
        + ", ".join(sorted(set(missing + stale_critical)))
    )
print(
    "✅ Macro event contract " + MACRO_EVENT_INPUT_SCHEMA_VERSION
    + " validated; keys=" + str(len(MACRO_INPUT_KEYS))
)
print(
    "📡 Data freshness: fresh=" + str(freshness["fresh_count"])
    + ", stale=" + str(freshness["stale_count"])
    + ", missing=" + str(freshness["missing_count"])
)

macro_system = MacroEventInterpretationSystem()
results = macro_system.evaluate_history(normalized_input)
if results.empty:
    raise RuntimeError("MacroEventInterpretationSystem boş sonuç döndürdü.")

last = results.iloc[-1]
computed_confirmed_id = int(last["confirmed_regime_id"])
candidate_id = int(last["candidate_regime_id"])
subtype = str(last["subtype"])
in_transition = bool(last["in_transition"])
extreme_event = bool(last.get("extreme_event", False))

continuum = compute_continuum_regime_state(
    last,
    confirmed_regime_id=computed_confirmed_id,
    candidate_regime_id=candidate_id,
    in_transition=in_transition,
)
structural = continuum.get("structural_state", compute_structural_risk_state(last))
fingerprint = data_fingerprint(normalized_input)

circuit_triggered, circuit_reasons = compute_circuit_breaker({
    "move": yf_data["move"],
    "hy_oas": fred_data["hy_oas"],
    "nfci": fred_data["nfci"],
    "vix": yf_data["vix"],
})

# 3) Persistent state is the continuity/audit layer.
if os.path.exists(SUMMARY_PATH):
    try:
        with open(SUMMARY_PATH, "r", encoding="utf-8") as handle:
            summary = json.load(handle)
    except Exception:
        summary = {}
else:
    summary = {}

monitor = summary.get("autonomous_daily_monitor", {})
previous_current = monitor.get("current", {}) if isinstance(monitor, dict) else {}
previous_confirmed = previous_current.get("confirmed_regime_id")
previous_candidate = previous_current.get("candidate_regime_id")
previous_circuit = previous_current.get("circuit_breaker_triggered")

# The core historical state machine is authoritative. A persisted
# regime change is accepted only when the engine is out of transition.
if previous_confirmed is None:
    final_id = computed_confirmed_id
    action = "INITIALIZE"
elif computed_confirmed_id != int(previous_confirmed):
    if not in_transition:
        final_id = computed_confirmed_id
        action = "REGIME_CHANGE"
    else:
        final_id = int(previous_confirmed)
        action = "HOLD_PREVIOUS_DURING_TRANSITION"
else:
    final_id = int(previous_confirmed)
    action = "HOLD"

final_name = REGIME_NAMES.get(final_id, "REJIMSIZ_GECIS")
continuum_dominant = str(continuum["dominant_regime"])
continuum_probs = {k: float(v) for k, v in continuum["regime_probs"].items()}

if final_id == 3:
    continuum_agrees = continuum_dominant in {"DEFLASYON", "STAGFLASYON"}
else:
    mapped_continuum = CONTINUUM_REGIME_MAP.get(final_id)
    continuum_agrees = True if mapped_continuum is None else continuum_dominant == mapped_continuum

# 4) Explicit portfolio allocation: macro regime, risk appetite and cash are separate.
active_multipliers = get_macro_interpretation_asset_multipliers(final_id, subtype)
# Same 8-asset signal scan as the Streamlit app, so the persisted portfolio
# matches what the UI shows for the same data.
asset_signals = {}
asset_signal_scores = {}
factor_scores_snapshot = {}
try:
    from asset_signal_engine import (
        build_g4_net_liquidity, compute_all_asset_signals, compute_factor_scores, safe_spread,
    )
    horizon_start = pd.Timestamp.now(tz="UTC").tz_localize(None) - pd.Timedelta(days=2500)
    trim = lambda s: s[s.index >= horizon_start] if isinstance(s, pd.Series) and not s.empty else s
    factor_inputs = {
        "dxy": trim(yf_data["dxy"]),
        "g4_liq": trim(build_g4_net_liquidity(fred_data["walcl"], fred_data["tga"], fred_data["rrp"],
                                              fred_data["ecb"], yf_data["eurusd"], fred_data["boj"], yf_data["usdjpy"])),
        "dfii10": trim(fred_data["dfii10"]), "t10yie": trim(fred_data["t10yie"]),
        "t5yifr": trim(fred_data["t5yifr"]),
        "fed_easing_spread": trim(safe_spread(fred_data["effr"], fred_data["ust2y"])),
        "hy_oas": trim(fred_data["hy_oas"]), "move": trim(yf_data["move"]), "vix": trim(yf_data["vix"]),
        "t10y2y": trim(fred_data["t10y2y"]), "icsa": trim(fred_data["icsa"]),
        "wresbal": trim(fred_data["wresbal"]),
    }
    factor_scores_snapshot = compute_factor_scores(factor_inputs)
    asset_prices = {
        "Altın (XAU)": trim(yf_data["gold"]), "Gümüş (XAG)": trim(yf_data["xag"]),
        "Nasdaq 100 (NQ)": trim(yf_data["qqq"]), "S&P 500 (SPX)": trim(yf_data["spx"]),
        "Kripto (BTC)": trim(yf_data["btc"]), "Ham Petrol (WTI)": trim(yf_data["oil"]),
        "Bakır (HG)": trim(yf_data["hg"]), "ABD Tahvili / Faiz (TLT)": trim(yf_data["tlt"]),
    }
    scan = compute_all_asset_signals(
        {k: v["z"] for k, v in factor_scores_snapshot.items()}, asset_prices, structural,
        final_id, subtype, continuum_probs, in_transition,
    )
    for asset_name, st_ in scan.items():
        asset_signal_scores[asset_name] = float(st_["score"])
        asset_signals[asset_name] = {
            "label": st_["label"], "score": float(st_["score"]), "confidence": float(st_["confidence"]),
            "macro_component": float(st_["macro_component"]), "market_component": float(st_["market_component"]),
            "structure_component": float(st_["structure_component"]),
        }
except Exception as exc:
    print(f"[WARN] asset signal scan skipped: {exc}")

# v3.0: long-horizon cycle signals (al-unut / sat-unut) per asset
cycle_signals = {}
try:
    from cycle_engine import current_cycle_signal, load_cycle_params
    _cparams = load_cycle_params()
    _cprices = {
        "Altın (XAU)": yf_data["gold"], "Gümüş (XAG)": yf_data["xag"], "Nasdaq 100 (NQ)": yf_data["qqq"],
        "S&P 500 (SPX)": yf_data["spx"], "Kripto (BTC)": yf_data["btc"], "Ham Petrol (WTI)": yf_data["oil"],
        "Bakır (HG)": yf_data["hg"], "ABD Tahvili / Faiz (TLT)": yf_data["tlt"],
    }
    for _a, _s in _cprices.items():
        cycle_signals[_a] = current_cycle_signal(_a, _s, _cparams.get(_a))
except Exception as exc:
    print(f"[WARN] cycle signals failed: {exc}")

# v2.5: target = regime MINIMUM-DRAWDOWN portfolio (regime_portfolio.py),
# identical to the Streamlit "🎯 Hedef Portföy" page (same 2500-day window).
regime_portfolio_summary = {}
try:
    from regime_portfolio import active_target_weights, compute_regime_portfolios
    _prices = {
        "Altın (XAU)": yf_data["gold"], "Gümüş (XAG)": yf_data["xag"], "Nasdaq 100 (NQ)": yf_data["qqq"],
        "S&P 500 (SPX)": yf_data["spx"], "Kripto (BTC)": yf_data["btc"], "Ham Petrol (WTI)": yf_data["oil"],
        "Bakır (HG)": yf_data["hg"], "ABD Tahvili / Faiz (TLT)": yf_data["tlt"],
    }
    _ports = compute_regime_portfolios(results["confirmed_regime_id"], _prices, lookback_days=2500)
    from regime_portfolio import selected_strategy, strategy_weights
    _strategy = selected_strategy()
    from regime_portfolio import STRATEGY_LABELS
    _cache = {}
    all_strategy_targets = {}
    for _s in STRATEGY_LABELS:
        try:
            all_strategy_targets[_s] = strategy_weights(
                _s, _prices, results["confirmed_regime_id"], final_id, candidate_id, in_transition, regime_cache=_cache)
        except Exception as _exc:
            print(f"[WARN] strategy {_s} failed: {_exc}")
    target_portfolio_weights = all_strategy_targets.get(_strategy) or strategy_weights(
        _strategy, _prices, results["confirmed_regime_id"], final_id, candidate_id, in_transition
    )
    regime_portfolio_summary = {
        str(rid): {"weights": p["weights"], "trust": p["trust"], "stats": p["stats"], "ew_stats": p["ew_stats"]}
        for rid, p in _ports.get("portfolios", {}).items()
    }
except Exception as exc:
    print(f"[WARN] regime min-drawdown portfolio failed, using legacy weights: {exc}")
    target_portfolio_weights = compute_target_portfolio_weights(
        final_id, subtype, structural, asset_signal_scores=asset_signal_scores or None
    )
asset_snapshot = {}
for asset in ASSETS:
    indicator_weights = get_dynamic_asset_weights(asset, final_id, continuum_probs, in_transition=in_transition)
    raw_macro_mult=float(active_multipliers.get(asset, 1.0))
    asset_snapshot[asset] = {
        "macro_exposure_multiplier_raw": raw_macro_mult,
        "macro_exposure_multiplier_effective": float(compute_effective_macro_asset_multiplier(asset, raw_macro_mult, structural)),
        "structural_asset_tilt": float(compute_portfolio_asset_tilt(asset, structural)),
        "target_portfolio_weight_pct": float(target_portfolio_weights.get(asset, 0.0)),
        "structural_state": structural.get("state"),
        "portfolio_risk_budget_pct": float(structural.get("portfolio_risk_budget", 0.50) * 100.0),
        "cash_target_pct": float(structural.get("cash_target_pct", 50.0)),
        "indicator_weights": {name: float(indicator_weights.get(name, 0.0)) for name in INDICATORS},
    }

now_utc = datetime.now(timezone.utc)
today_utc = now_utc.date().isoformat()
current_state = {
    "observed_at_utc": now_utc.isoformat(),
    "observation_date_utc": today_utc,
    "confirmed_regime_id": final_id,
    "confirmed_regime_name": final_name,
    "computed_historical_confirmed_regime_id": computed_confirmed_id,
    "candidate_regime_id": candidate_id,
    "candidate_regime_name": REGIME_NAMES.get(candidate_id, "REJIMSIZ_GECIS"),
    "subtype": subtype,
    "in_transition": in_transition,
    "extreme_event": extreme_event,
    "action": action,
    "previous_confirmed_regime_id": previous_confirmed,
    "previous_candidate_regime_id": previous_candidate,
    "continuum_dominant_regime": continuum_dominant,
    "continuum_regime_title": continuum["regime_title"],
    "continuum_probabilities": continuum_probs,
    "continuum_deterministic_agreement": bool(continuum_agrees),
    "continuum_diagnostics": continuum["diagnostics"],
    "structural_state": structural,
    "portfolio_risk_budget_pct": float(structural.get("portfolio_risk_budget", 0.50) * 100.0),
    "cash_target_pct": float(structural.get("cash_target_pct", 50.0)),
    "target_portfolio_weights_pct": target_portfolio_weights,
    "data_fingerprint": fingerprint,
    "data_freshness": freshness,
    "circuit_breaker_triggered": bool(circuit_triggered),
    "circuit_breaker_reasons": circuit_reasons,
    "data_health": {
        "contract_schema_version": MACRO_EVENT_INPUT_SCHEMA_VERSION,
        "contract_key_count": len(MACRO_INPUT_KEYS),
        "critical_key_count": len(CRITICAL_INPUT_KEYS),
        "critical_missing_series": missing,
        "critical_stale_series": stale_critical,
        "series_count": len(normalized_input),
        "evaluated_rows": int(len(results)),
        "latest_feature_date": str(results.index[-1]),
        "latest_source_observation_by_series": {
            key: (pd.Timestamp(series.index[-1]).isoformat() if not series.empty else None)
            for key, series in normalized_input.items()
        },
        "fresh_count": int(freshness["fresh_count"]),
        "stale_count": int(freshness["stale_count"]),
        "missing_count": int(freshness["missing_count"]),
    },
    "asset_allocation_snapshot": asset_snapshot,
    "asset_signals": asset_signals,
    "regime_min_drawdown_portfolios": regime_portfolio_summary,
    "portfolio_strategy": locals().get("_strategy"),
    "all_strategy_targets": locals().get("all_strategy_targets", {}),
    "cycle_signals": locals().get("cycle_signals", {}),
    "factor_scores": factor_scores_snapshot,
}

# Persist at least once per UTC day, plus every material regime/circuit change.
history = monitor.get("history", []) if isinstance(monitor, dict) else []
if not isinstance(history, list):
    history = []

previous_fingerprint = previous_current.get("data_fingerprint")
previous_structural = previous_current.get("structural_state", {}) if isinstance(previous_current, dict) else {}
material_structural_change = (
    previous_confirmed is None
    or abs(float(structural.get("risk_appetite_score",0.50)) - float(previous_structural.get("risk_appetite_score",0.50))) >= 0.07
    or abs(float(structural.get("tightening_score",0.50)) - float(previous_structural.get("tightening_score",0.50))) >= 0.07
    or abs(float(structural.get("cash_target_pct",50.0)) - float(previous_current.get("cash_target_pct",50.0))) >= 5.0
    or abs(float(structural.get("risk_rotation_20",0.50)) - float(previous_structural.get("risk_rotation_20",0.50))) >= 0.10
)
previous_labels = {k: (v or {}).get("label") for k, v in (previous_current.get("asset_signals") or {}).items()} if isinstance(previous_current, dict) else {}
prev_cycle = {k: (v or {}).get("label") for k, v in (previous_current.get("cycle_signals") or {}).items()} if isinstance(previous_current, dict) else {}
cycle_change = bool(cycle_signals) and any(prev_cycle.get(k) != v.get("label") for k, v in cycle_signals.items())
signal_label_change = cycle_change or bool(asset_signals) and any(
    previous_labels.get(k) != v.get("label") for k, v in asset_signals.items()
)
should_persist = (
    signal_label_change
    or previous_confirmed is None
    or previous_circuit is None
    or today_utc != str(previous_current.get("observation_date_utc", ""))
    or final_id != int(previous_confirmed)
    or candidate_id != (None if previous_candidate is None else int(previous_candidate))
    or bool(circuit_triggered) != bool(previous_circuit)
    or structural.get("state") != previous_structural.get("state")
    or material_structural_change
)

if should_persist:
    history.append({
        "timestamp_utc": now_utc.isoformat(),
        "action": action,
        "previous_confirmed_regime_id": previous_confirmed,
        "confirmed_regime_id": final_id,
        "candidate_regime_id": candidate_id,
        "confirmed_regime_name": final_name,
        "candidate_regime_name": REGIME_NAMES.get(candidate_id, "REJIMSIZ_GECIS"),
        "subtype": subtype,
        "in_transition": in_transition,
        "extreme_event": extreme_event,
        "continuum_dominant_regime": continuum_dominant,
        "continuum_probabilities": continuum_probs,
        "continuum_deterministic_agreement": bool(continuum_agrees),
        "structural_state": structural,
        "data_fingerprint": fingerprint,
        "data_freshness": freshness,
        "circuit_breaker_triggered": bool(circuit_triggered),
        "circuit_breaker_reasons": circuit_reasons,
        "data_health": current_state["data_health"],
    })
    history = history[-365:]
    summary["autonomous_daily_monitor"] = {
        "status": "ACTIVE",
        "schedule": "Every 2 hours (UTC); persisted whenever source data changes, structural state changes, circuit state changes, or at least daily",
        "architecture": [
            "scheduled_fresh_data_fetch_with_retries",
            "intraday_evaluation_without_commit_spam",
            "source_data_freshness_guard",
            "source_freshness_validation",
            "canonical_contract_normalization",
            "normalized_event_features",
            "multi_horizon_risk_appetite_and_cross_asset_rotation",
            "bank_and_small_cap_participation_confirmation",
            "explicit_target_portfolio_weights",
            "deterministic_event_engine",
            "continuum_regime_engine",
            "hysteresis_and_extreme_event_confirmation",
            "persistent_state_arbitration",
            "dynamic_asset_allocation",
            "systemic_circuit_breaker",
            "daily_audit_history",
        ],
        "current": current_state,
        "history": history,
        "last_persisted_at_utc": now_utc.isoformat(),
    }
    with open(SUMMARY_PATH, "w", encoding="utf-8") as handle:
        json.dump(json_safe(summary), handle, indent=2, ensure_ascii=False, allow_nan=False)
    print("✅ Autonomous state persisted.")
else:
    print("ℹ️ Fresh data were evaluated, but the persisted state fingerprint is unchanged; repository file is not rewritten.")

print(json.dumps(json_safe({
    "checked_at_utc": now_utc.isoformat(),
    "confirmed_regime_id": final_id,
    "candidate_regime_id": candidate_id,
    "continuum": continuum_dominant,
    "structural_state": structural.get("state"),
    "risk_appetite_score": structural.get("risk_appetite_score"),
    "tightening_score": structural.get("tightening_score"),
    "cash_target_pct": structural.get("cash_target_pct"),
    "circuit_breaker": circuit_triggered,
    "persisted": should_persist,
}), ensure_ascii=False))
