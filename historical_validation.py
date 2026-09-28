"""
Historical Validation — real data, point-in-time, "dipten al / tepeden sat" test
==================================================================================
backtest_regimes.py validates the model on SYNTHETIC data whose price paths
were hand-written to match each regime hypothesis (its own summary says
performance_claims_valid_for_live_markets = False). Sharpe ratios of 3-4 for
buy-and-hold-like strategies in asset_dynamic_backtest_results.csv are a
symptom of that: the answer is baked into the data.

This module measures the REAL system on REAL history:

1. Downloads daily history (FRED via the public fredgraph CSV endpoint -- no
   API key needed -- and Yahoo Finance), then shifts every series by its
   PUBLICATION LAG (e.g. ICSA is dated to the week-ending Saturday but only
   released the following Thursday; DTWEXBGS is published ~1 week late), so
   each historical date only sees data that was actually public then.
2. Runs the production regime engine (MacroEventInterpretationSystem) once
   over the whole lagged history. Every feature is a trailing rolling
   statistic, so each row is point-in-time by construction.
3. Every `step` business days, recomputes the production 12-factor scores
   and the 8-asset signal scan (asset_signal_engine -> the SAME code the app
   and the autonomous monitor run) with all series sliced to that date.
4. Reports, per asset:
   * Information coefficient of the signal score AND of each component
     (macro / market / structure) versus forward 20/60/120-day returns.
   * Hit-rates of the AL / SAT labels.
   * THE TOP/BOTTOM TEST: correlation between the score and where price sits
     in its own 1-year range (0 = at the 1y low, 1 = at the 1y high), and the
     average score near 1-year highs vs near 1-year lows. A system meant to
     "buy low, sell high" should score LOW near highs and HIGH near lows.
   * Regime-onset study: forward returns after each regime is first
     confirmed, compared with the direction the regime multipliers take.
   * A weekly-rebalanced portfolio using the model's target weights vs an
     equal-weight benchmark (real Sharpe, max drawdown, 5 bps turnover cost).

Usage:
    python historical_validation.py                      # download + run
    python historical_validation.py --years 10 --step 5
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from io import StringIO
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

# FRED id -> publication lag in BUSINESS days after the observation date
FRED_SERIES = {
    "DGS2": 1, "DGS10": 1, "DFII10": 1, "T10YIE": 1, "T5YIFR": 1, "EFFR": 1, "T10Y2Y": 1,
    "BAMLH0A0HYM2": 1, "BAMLC0A0CM": 1,
    "DTWEXBGS": 5,     # H.10 broad dollar: published about one week late
    "NFCI": 3,         # week ending Friday, released the following Wednesday
    "ICSA": 4,         # week ending Saturday, released the following Thursday
    "WALCL": 1, "WTREGEN": 1, "WRESBAL": 1,  # Wednesday level, released Thursday
    "RRPONTSYD": 1,
    "ECBASSETSW": 2,
    "JPNASSETS": 25,   # monthly, published the following month
}
YAHOO_SERIES = {
    "oil": "CL=F", "bdi": "BDRY", "dxy": "DX-Y.NYB", "usdjpy": "JPY=X", "vix": "^VIX",
    "move": "^MOVE", "btc": "BTC-USD", "spx": "SPY", "gold": "GC=F", "xag": "SI=F",
    "hg": "HG=F", "dbb": "DBB", "eurusd": "EURUSD=X", "bank_equity": "XLF",
    "small_caps": "IWM", "qqq": "QQQ", "tlt": "TLT",
}
ASSET_PRICE_KEYS = {
    "Altın (XAU)": "gold", "Gümüş (XAG)": "xag", "Nasdaq 100 (NQ)": "qqq",
    "S&P 500 (SPX)": "spx", "Kripto (BTC)": "btc", "Ham Petrol (WTI)": "oil",
    "Bakır (HG)": "hg", "ABD Tahvili / Faiz (TLT)": "tlt",
}
HORIZONS = (20, 60, 120)


# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------
def _clean(s: pd.Series) -> pd.Series:
    s = pd.Series(s).copy()
    s.index = pd.to_datetime(s.index, errors="coerce")
    s = s[~s.index.isna()]
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    s = pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().sort_index()
    return s[~s.index.duplicated(keep="last")].astype(float)


def fetch_fred(series_id: str, start: str) -> pd.Series:
    import requests
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            df = pd.read_csv(StringIO(r.text))
            date_col = next((c for c in df.columns if c.lower() in {"date", "observation_date"}), df.columns[0])
            val_col = [c for c in df.columns if c != date_col][0]
            vals = pd.to_numeric(df[val_col].replace(".", np.nan), errors="coerce")
            return _clean(pd.Series(vals.values, index=pd.to_datetime(df[date_col], errors="coerce")))
        except Exception:
            time.sleep(2 ** attempt)
    return pd.Series(dtype=float)


def fetch_yahoo(ticker: str, years: int) -> pd.Series:
    import yfinance as yf
    for attempt in range(3):
        try:
            d = yf.download(ticker, period=f"{years}y", interval="1d", auto_adjust=False,
                            progress=False, threads=False, timeout=30)
            if d is None or d.empty:
                raise ValueError("empty")
            if isinstance(d.columns, pd.MultiIndex):
                s = d["Close"] if "Close" in d.columns.get_level_values(0) else d.iloc[:, 0]
            else:
                s = d["Close"] if "Close" in d.columns else d.iloc[:, 0]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            return _clean(s)
        except Exception:
            time.sleep(2 ** attempt)
    return pd.Series(dtype=float)


def apply_publication_lag(s: pd.Series, lag_bdays: int) -> pd.Series:
    """Re-date each observation to the business day it became public."""
    if s.empty or lag_bdays <= 0:
        return s
    out = s.copy()
    out.index = out.index + pd.offsets.BDay(int(lag_bdays))
    return out[~out.index.duplicated(keep="last")]


def download_all(years: int, cache_dir: Optional[str] = None) -> Dict[str, pd.Series]:
    start = (pd.Timestamp.now() - pd.DateOffset(years=years + 2)).strftime("%Y-%m-%d")
    data: Dict[str, pd.Series] = {}
    for sid, lag in FRED_SERIES.items():
        data[f"fred:{sid}"] = apply_publication_lag(fetch_fred(sid, start), lag)
        time.sleep(0.3)
    for key, tic in YAHOO_SERIES.items():
        data[key] = fetch_yahoo(tic, years + 2)
        time.sleep(0.3)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        pd.DataFrame(data).to_csv(os.path.join(cache_dir, "validation_inputs.csv"))
    return data


def load_cache(path: str) -> Dict[str, pd.Series]:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return {c: _clean(df[c].dropna()) for c in df.columns}


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------
def _spearman(x: pd.Series, y: pd.Series) -> Optional[float]:
    d = pd.concat([x, y], axis=1).dropna()
    if len(d) < 20 or d.iloc[:, 0].nunique() < 3:
        return None
    return float(d.iloc[:, 0].rank().corr(d.iloc[:, 1].rank()))


def run_validation(data: Dict[str, pd.Series], years: int = 10, step: int = 5) -> Dict[str, object]:
    from macro_event_interpretation import (
        MacroEventInterpretationSystem, compute_continuum_regime_state, compute_net_liquidity,
        compute_structural_risk_state, compute_target_portfolio_weights,
        get_macro_interpretation_asset_multipliers,
    )
    from asset_signal_engine import (
        build_g4_net_liquidity, compute_all_asset_signals, compute_factor_scores, safe_spread,
    )

    F = lambda sid: data.get(f"fred:{sid}", pd.Series(dtype=float))
    Y = lambda k: data.get(k, pd.Series(dtype=float))
    dtwex = F("DTWEXBGS") if not F("DTWEXBGS").empty else Y("dxy")
    ndl = compute_net_liquidity(F("WALCL"), F("WTREGEN"), F("RRPONTSYD"))
    macro_input = {
        "oil": Y("oil"), "bdi": Y("bdi"), "hy_oas": F("BAMLH0A0HYM2"), "ig_oas": F("BAMLC0A0CM"),
        "spx": Y("spx"), "ust10y": F("DGS10"), "ust2y": F("DGS2"), "dtwex": dtwex, "dxy": Y("dxy"),
        "usdjpy": Y("usdjpy"), "vix": Y("vix"), "move": Y("move"), "btc": Y("btc"),
        "dfii10": F("DFII10"), "t10yie": F("T10YIE"), "ndl": ndl, "gold": Y("gold"), "xag": Y("xag"),
        "hg": Y("hg"), "dbb": Y("dbb"), "nfci": F("NFCI"), "icsa": F("ICSA"),
        "bank_equity": Y("bank_equity"), "small_caps": Y("small_caps"),
    }
    results = MacroEventInterpretationSystem().evaluate_history(macro_input)

    factor_inputs = {
        "dxy": Y("dxy"),
        "g4_liq": build_g4_net_liquidity(F("WALCL"), F("WTREGEN"), F("RRPONTSYD"), F("ECBASSETSW"),
                                         Y("eurusd"), F("JPNASSETS"), Y("usdjpy")),
        "dfii10": F("DFII10"), "t10yie": F("T10YIE"), "t5yifr": F("T5YIFR"),
        "fed_easing_spread": safe_spread(F("EFFR"), F("DGS2")), "hy_oas": F("BAMLH0A0HYM2"),
        "move": Y("move"), "vix": Y("vix"), "t10y2y": F("T10Y2Y"), "icsa": F("ICSA"),
        "wresbal": F("WRESBAL"),
    }
    prices = {a: Y(k) for a, k in ASSET_PRICE_KEYS.items()}
    bgrid = pd.bdate_range(results.index.min(), results.index.max())
    px = pd.DataFrame({a: s.reindex(bgrid, method="ffill") for a, s in prices.items() if not s.empty})

    start = results.index.max() - pd.DateOffset(years=years)
    start = max(start, results.index.min() + pd.DateOffset(years=2))
    dates = [d for d in results.index[results.index >= start]][::step]

    rows: List[Dict[str, object]] = []
    weights_rows: List[Dict[str, float]] = []
    mindd_rows: List[Dict[str, float]] = []
    factor_rows: List[Dict[str, float]] = []
    from regime_portfolio import active_target_weights, compute_regime_portfolios
    regime_ports = None
    t0 = time.time()
    for i, t in enumerate(dates):
        row = results.loc[t]
        conf, cand, tr = int(row["confirmed_regime_id"]), int(row["candidate_regime_id"]), bool(row["in_transition"])
        subtype = str(row["subtype"])
        structural = compute_structural_risk_state(row)
        cont = compute_continuum_regime_state(row, confirmed_regime_id=conf, candidate_regime_id=cand, in_transition=tr)
        horizon_start = t - pd.Timedelta(days=2500)   # the app/monitor use the last ~2500 days
        sliced = {k: v[(v.index <= t) & (v.index >= horizon_start)] for k, v in factor_inputs.items()}
        fs = compute_factor_scores(sliced)
        pr = {a: s[(s.index <= t) & (s.index >= horizon_start)] for a, s in prices.items()}
        scan = compute_all_asset_signals({k: v["z"] for k, v in fs.items()}, pr, structural, conf, subtype,
                                         cont["regime_probs"], tr)
        w = compute_target_portfolio_weights(conf, subtype, structural,
                                             asset_signal_scores={a: s["score"] for a, s in scan.items()})
        weights_rows.append({"date": t, **w})
        factor_rows.append({"date": t, **{k: v["z"] for k, v in fs.items()}})
        # OUT-OF-SAMPLE min-drawdown regime portfolio: re-optimised every ~60
        # business days using ONLY data up to t (regime labels and prices).
        if regime_ports is None or i % max(1, 60 // step) == 0:
            try:
                regime_ports = compute_regime_portfolios(
                    results["confirmed_regime_id"][results.index <= t], prices, lookback_days=2500, as_of=t)
            except Exception:
                pass
        if regime_ports is not None:
            mindd_rows.append({"date": t, **active_target_weights(
                regime_ports, conf, cand, tr, structural.get("portfolio_risk_budget", 0.5))})
        for asset, st in scan.items():
            s = pr.get(asset)
            if s is None or len(s) < 260:
                continue
            last = float(s.iloc[-1]); hist = s.tail(252)
            lo, hi = float(hist.min()), float(hist.max())
            range_pos = (last - lo) / (hi - lo) if hi > lo else 0.5
            rec = {
                "date": t, "asset": asset, "score": st["score"], "label": st["label"],
                "macro": st["macro_component"], "market": st["market_component"],
                "structure": st["structure_component"], "range_pos_1y": range_pos,
                "drawdown_1y": last / hi - 1.0, "regime": conf,
            }
            if asset in px.columns:
                p0 = px[asset].asof(t)
                for h in HORIZONS:
                    tgt = t + pd.offsets.BDay(h)
                    rec[f"fwd{h}"] = (float(px[asset].asof(tgt)) / p0 - 1.0) if tgt <= px.index[-1] and p0 else np.nan
            rows.append(rec)
        if (i + 1) % 50 == 0:
            print(f"[validation] {i + 1}/{len(dates)} tarih · {(time.time() - t0) / (i + 1):.2f}s/tarih", flush=True)

    sig = pd.DataFrame(rows)
    wts = pd.DataFrame(weights_rows).set_index("date") if weights_rows else pd.DataFrame()
    mindd = pd.DataFrame(mindd_rows).set_index("date") if mindd_rows else pd.DataFrame()
    factors = pd.DataFrame(factor_rows).set_index("date") if factor_rows else pd.DataFrame()
    return {"signals": sig, "weights": wts, "mindd_weights": mindd, "factors": factors,
            "results": results, "prices": px, "step": step}


# ----------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------
def _ic_block(sig: pd.DataFrame, step: int) -> List[str]:
    L = ["## 2) Sinyal bilgi katsayısı (IC) — skor gerçekten ileriyi gösteriyor mu?",
         "IC = skor ile sonraki getirinin sıra korelasyonu. Pozitif = doğru yön. "
         "|t| ≥ 2 istatistiksel olarak güvenilir (çakışan ufuklar için bağımsız örnek sayısıyla).", "",
         "| Varlık | Bileşen | IC 20g | IC 60g | IC 120g | t(60g) | n |", "|---|---|---|---|---|---|---|"]
    for asset in sorted(sig["asset"].unique()):
        a = sig[sig["asset"] == asset]
        for comp in ("score", "macro", "market", "structure"):
            ics = {h: _spearman(a[comp], a[f"fwd{h}"]) for h in HORIZONS if f"fwd{h}" in a}
            n = int(a["fwd60"].notna().sum()) if "fwd60" in a else 0
            n_ind = max(1.0, n * step / 60.0)
            t60 = None if ics.get(60) is None else ics[60] * math.sqrt(n_ind)
            f = lambda v: "—" if v is None else f"{v:+.3f}"
            name = {"score": "**TOPLAM SKOR**", "macro": "makro", "market": "piyasa (trend+zirve yakınlığı)",
                    "structure": "risk döngüsü"}[comp]
            L.append(f"| {asset} | {name} | {f(ics.get(20))} | {f(ics.get(60))} | {f(ics.get(120))} | "
                     f"{'—' if t60 is None else f'{t60:+.1f}'} | {n} |")
    L.append("")
    return L


def _top_bottom_block(sig: pd.DataFrame) -> List[str]:
    L = ["## 1) TEPE / DİP TESTİ — sistem \"dipten al, tepeden sat\" yapıyor mu?",
         "Konum = fiyatın kendi 1 yıllık aralığındaki yeri (0 = 1 yılın dibi, 1 = 1 yılın zirvesi). "
         "Dipten alan bir sistemde skor ile konum arasındaki korelasyon **negatif** olmalı "
         "(zirvede düşük skor, dipte yüksek skor). Pozitif korelasyon = zirvede AL, dipte SAT (momentum takibi).", "",
         "| Varlık | Skor~Konum korelasyonu | Ort. skor 1y zirve yakını (konum>0.9) | Ort. skor 1y dip yakını (konum<0.1) | "
         "Zirvede sonraki 60g getiri | Dipte sonraki 60g getiri |", "|---|---|---|---|---|---|"]
    for asset in sorted(sig["asset"].unique()):
        a = sig[sig["asset"] == asset]
        c = _spearman(a["score"], a["range_pos_1y"])
        top, bot = a[a["range_pos_1y"] > 0.9], a[a["range_pos_1y"] < 0.1]
        f = lambda x: "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.1f}"
        pct = lambda x: "—" if x is None or np.isnan(x) else f"%{x * 100:+.1f}"
        L.append(f"| {asset} | {'—' if c is None else f'{c:+.2f}'} | {f(top['score'].mean() if len(top) else None)} (n={len(top)}) | "
                 f"{f(bot['score'].mean() if len(bot) else None)} (n={len(bot)}) | "
                 f"{pct(top['fwd60'].mean() if len(top) else np.nan)} | {pct(bot['fwd60'].mean() if len(bot) else np.nan)} |")
    L.append("")
    return L


def _label_block(sig: pd.DataFrame) -> List[str]:
    L = ["## 3) Etiket isabeti (60 gün sonrası)", "",
         "| Varlık | AL/GÜÇLÜ AL: isabet · ort getiri (n) | AZALT/SAT: isabet · ort getiri (n) | Koşulsuz: yükseliş oranı · ort getiri |",
         "|---|---|---|---|"]
    for asset in sorted(sig["asset"].unique()):
        a = sig[sig["asset"] == asset].dropna(subset=["fwd60"])
        buy = a[a["label"].str.contains("AL") & ~a["label"].str.contains("SAT")]
        sell = a[a["label"].str.contains("AZALT|SAT")]
        g = lambda d, up: "—" if d.empty else f"%{((d['fwd60'] > 0) if up else (d['fwd60'] < 0)).mean() * 100:.0f} · %{d['fwd60'].mean() * 100:+.1f} ({len(d)})"
        L.append(f"| {asset} | {g(buy, True)} | {g(sell, False)} | "
                 f"%{(a['fwd60'] > 0).mean() * 100:.0f} · %{a['fwd60'].mean() * 100:+.1f} |")
    L.append("")
    return L


def _regime_onset_block(results: pd.DataFrame, px: pd.DataFrame) -> List[str]:
    from macro_event_interpretation import REGIME_NAMES, get_macro_interpretation_asset_multipliers
    conf = results["confirmed_regime_id"].astype(int)
    onsets = conf[(conf != conf.shift(1)) & (conf != 0)]
    L = ["## 4) Rejim başlangıcı sonrası getiriler — rejim çarpanları doğru yönde mi?",
         "Her rejim ilk onaylandığında sonraki 60 iş günü getirisi (ortalama) ve modelin o rejimde verdiği çarpan. "
         "Çarpan < 1 (azalt) iken getiri güçlü pozitifse, rejim kuralı **dipte satıyor** demektir.", ""]
    assets = list(px.columns)
    L.append("| Rejim | Başlangıç sayısı | " + " | ".join(f"{a.split(' (')[0]} 60g (çarpan)" for a in assets) + " |")
    L.append("|---|---|" + "---|" * len(assets))
    for rid in sorted(onsets.unique()):
        ds = onsets[onsets == rid].index
        mult = get_macro_interpretation_asset_multipliers(int(rid), "")
        cells = []
        for a in assets:
            rets = []
            for d in ds:
                tgt = d + pd.offsets.BDay(60)
                if tgt <= px.index[-1]:
                    p0 = px[a].asof(d); p1 = px[a].asof(tgt)
                    if p0 and p1 and np.isfinite(p0) and np.isfinite(p1):
                        rets.append(p1 / p0 - 1)
            cells.append("—" if not rets else f"%{np.mean(rets) * 100:+.1f} ({mult.get(a, 1.0):.2f}x)")
        L.append(f"| {rid}: {REGIME_NAMES.get(int(rid), '')} | {len(ds)} | " + " | ".join(cells) + " |")
    uncond = []
    for a in assets:
        r = (px[a].shift(-60) / px[a] - 1).dropna()
        uncond.append(f"%{r.mean() * 100:+.1f}")
    L.append("| Koşulsuz (tüm günler) | — | " + " | ".join(uncond) + " |")
    L.append("")
    return L


def _strategy_returns(wts: pd.DataFrame, rets: pd.DataFrame) -> pd.Series:
    assets = [a for a in wts.columns if a in rets.columns]
    w = wts[assets].div(100.0).reindex(rets.index).ffill().shift(1).fillna(0.0)   # trade next day
    turnover = w.diff().abs().sum(axis=1).fillna(0.0)
    return (w * rets[assets]).sum(axis=1) - turnover * 0.0005


def _portfolio_block(wts: pd.DataFrame, px: pd.DataFrame, mindd: pd.DataFrame = None) -> List[str]:
    L = ["## 5) Portföy testi — hedef ağırlıklar vs eşit ağırlık (örneklem dışı, işlem ertesi gün)", ""]
    if wts.empty:
        return L + ["- Veri yok."]
    rets = px.pct_change().fillna(0.0)
    first = wts.index[0]
    strategies = []
    if mindd is not None and not mindd.empty:
        r = _strategy_returns(mindd, rets)
        strategies.append(("🎯 Min-DD rejim portföyü (yeni hedef, her çeyrek yalnızca geçmiş veriyle yeniden optimize)", r[r.index > first]))
        # same weights fully invested (no cash) -> isolates the optimiser from the cash decision
        inv = mindd.drop(columns=["Nakit / Likit Rezerv"], errors="ignore")
        inv = inv.div(inv.sum(axis=1).replace(0, np.nan), axis=0).fillna(0) * 100
        r2 = _strategy_returns(inv, rets)
        strategies.append(("🎯 Min-DD rejim portföyü — %100 yatırımda (nakitsiz)", r2[r2.index > first]))
    model = _strategy_returns(wts, rets)
    strategies.append(("Eski hedef (sinyal × rejim çarpanı + nakit)", model[model.index > first]))
    eq = rets[[a for a in wts.columns if a in rets.columns]].mean(axis=1)
    strategies.append(("Eşit ağırlık 8 varlık (%100 yatırımda)", eq[eq.index > first]))

    def perf(r):
        cum = (1 + r).cumprod()
        yrs = len(r) / 252.0
        cagr = cum.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else 0
        vol = r.std() * math.sqrt(252)
        dd = (cum / cum.cummax() - 1).min()
        return cagr, vol, (cagr / vol if vol > 0 else 0), dd

    for name, r in strategies:
        c, v, s, d = perf(r)
        L.append(f"- **{name}:** yıllık getiri %{c * 100:+.1f} · volatilite %{v * 100:.1f} · Sharpe {s:.2f} · maks. düşüş %{d * 100:.1f}")
    avg_cash = wts.get("Nakit / Likit Rezerv", pd.Series(dtype=float)).mean()
    L.append(f"- Ortalama nakit payı: %{avg_cash:.0f}. (Karşılaştırma için: gerçek piyasada al-tut stratejilerinin Sharpe'ı genelde 0.3-0.9 aralığındadır; "
             "sentetik testteki 3-4'lük değerler bu yüzden gerçekçi değildi.)")
    L.append("")
    return L


def _factor_ic_block(sig: pd.DataFrame, factors: pd.DataFrame, step: int) -> List[str]:
    """IC of every macro factor, AS THE MODEL USES IT (z x asset polarity),
    vs the next 60 business days' return. Positive = the configured polarity
    points the right way; negative = that factor currently pushes this asset
    the WRONG way."""
    from macro_event_interpretation import ASSET_SIGNAL_POLARITY
    L = ["## 6) Faktör bazında IC — her makro gösterge her varlıkta doğru yönde mi?",
         "Değer = (gösterge z-skoru × modeldeki varlık kutbu) ile sonraki 60 iş günü getirisinin sıra korelasyonu. "
         "**Pozitif** = gösterge o varlığı doğru yöne itiyor; **negatif** = ters itiyor. "
         "± işaretli değerlerde |t| ≥ 2 (anlamlı) olanlar **kalın**.", ""]
    if factors is None or factors.empty or sig.empty:
        return L + ["- Veri yok.", ""]
    assets = sorted(sig["asset"].unique())
    L.append("| Gösterge | " + " | ".join(a.split(" (")[0] for a in assets) + " |")
    L.append("|---|" + "---|" * len(assets))
    for fac in factors.columns:
        cells = []
        for a in assets:
            pol = float(ASSET_SIGNAL_POLARITY.get(a, {}).get(fac, 0.0))
            sub = sig[sig["asset"] == a][["date", "fwd60"]].dropna().set_index("date")
            if pol == 0.0 or sub.empty:
                cells.append("—"); continue
            x = factors[fac].reindex(sub.index) * pol
            ic = _spearman(x, sub["fwd60"])
            if ic is None:
                cells.append("—"); continue
            tstat = ic * math.sqrt(max(1.0, len(sub) * step / 60.0))
            cells.append(f"**{ic:+.2f}**" if abs(tstat) >= 2 else f"{ic:+.2f}")
        L.append(f"| {fac} | " + " | ".join(cells) + " |")
    L.append("")
    return L


def write_report(out: Dict[str, object], path: str) -> None:
    sig: pd.DataFrame = out["signals"]  # type: ignore
    results: pd.DataFrame = out["results"]  # type: ignore
    px: pd.DataFrame = out["prices"]  # type: ignore
    wts: pd.DataFrame = out["weights"]  # type: ignore
    L = ["# 🧪 Makro Model — Gerçek Veriyle Tarihsel Doğrulama", "",
         f"_Oluşturma: {pd.Timestamp.now(tz='UTC').isoformat()} · dönem: {sig['date'].min().date() if len(sig) else '-'} → "
         f"{sig['date'].max().date() if len(sig) else '-'} · {out['step']} iş gününde bir değerlendirme_", "",
         "Sistem, her tarihte yalnızca o tarihte YAYIMLANMIŞ veriyi görerek (FRED yayın gecikmeleri uygulanarak) "
         "canlı uygulamanın ve otonom izleyicinin kullandığı AYNI kodla çalıştırıldı. Model bu rapordan öğrenmez.", ""]
    if sig.empty:
        L.append("- Sinyal üretilemedi (veri yetersiz).")
    else:
        L += _top_bottom_block(sig)
        L += _ic_block(sig, int(out["step"]))
        L += _label_block(sig)
        L += _regime_onset_block(results, px)
        L += _portfolio_block(wts, px, out.get("mindd_weights"))  # type: ignore
        L += _factor_ic_block(sig, out.get("factors"), int(out["step"]))  # type: ignore
    L += ["## Sınırlar",
          "- FRED değerleri güncel vintage (piyasa serileri nadiren revize edilir; ICSA/NFCI küçük revizyonlar alabilir).",
          "- ^MOVE ve BDRY gibi serilerin Yahoo geçmişi kısa olabilir; eksik günlerde motorun kendi geri dönüşleri çalışır.",
          "- İşlem maliyeti: dönüşüm başına 5 bps; vergi/kaldıraç yok."]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--step", type=int, default=5)
    ap.add_argument("--cache", type=str, default=None, help="validation_inputs.csv (çevrimdışı çalıştırma)")
    ap.add_argument("--out", type=str, default=os.path.join(REPO_DIR, "validation_reports"))
    args = ap.parse_args()
    data = load_cache(args.cache) if args.cache else download_all(args.years)
    out = run_validation(data, years=args.years, step=args.step)
    os.makedirs(args.out, exist_ok=True)
    write_report(out, os.path.join(args.out, "historical_validation_report.md"))
    sig: pd.DataFrame = out["signals"]  # type: ignore
    if len(sig):
        sig.to_csv(os.path.join(args.out, "historical_signals.csv"), index=False)
    print(json.dumps({"signals": int(len(sig)), "report": os.path.join(args.out, "historical_validation_report.md")}))


if __name__ == "__main__":
    main()
