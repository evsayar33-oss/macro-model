"""
Asset Signal Engine — single source of truth for the 12 macro factor scores
============================================================================
Before v2.4 this logic lived only inside app.py, so:
  * the GitHub Actions monitor could not compute per-asset signals at all and
    persisted target weights WITHOUT them (the UI and the automation showed
    different portfolios for the same data), and
  * nothing outside Streamlit could test or validate it.

It is now shared by app.py, the autonomous monitor and the historical
validator. Behaviour is identical to the previous app.py code except for two
documented bug fixes:

1. "Reel Faiz İndirgeme İvmesi (10Y TIPS)" was inverted TWICE (the
   "Reel Faiz" branch already maps LOW real yields to a positive score, and
   app.py additionally passed invert=True). Net effect: RISING real yields
   were scored as supportive for gold / Nasdaq / BTC. Fixed by not inverting
   again (INDICATOR_SPECS below).
2. "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)" never reached its intended
   level-anchor branch because the name check was case-sensitive ("5y5y"
   vs "5Y5Y"); it silently fell back to a generic EMA-trend score.
"""

from typing import Any, Callable, Dict, Optional

import numpy as np
import pandas as pd


def get_adaptive_anchor(data_series, theoretical_mean, theoretical_std, lookback=1260):
    if len(data_series) >= 252:
        eff_lookback = min(len(data_series), lookback)
        empirical_mean = float(data_series.tail(eff_lookback).mean())
        empirical_std = float(data_series.tail(eff_lookback).std())
        # %50 Teorik Standart + %50 5-Yıllık Gerçekleşen Çapa (Ömür Boyu Kalibrasyon)
        mu_eff = 0.50 * theoretical_mean + 0.50 * empirical_mean
        std_eff = 0.50 * theoretical_std + 0.50 * max(empirical_std, 1e-4)
        return mu_eff, std_eff
    return theoretical_mean, theoretical_std

def process_indicator(data_series, indicator_name, invert=False):
    if isinstance(data_series, pd.DataFrame):
        data_series = data_series.iloc[:, 0]
        
    data_series = data_series.dropna()
    
    if len(data_series) < 30:
        val = float(data_series.iloc[-1]) if not data_series.empty else 0.0
        return 0.0, val
    
    current_val = float(data_series.iloc[-1])
    
    # 5 YILLIK HİBRİT BAYESYEN ÇAPALARLA HESAPLAMA
    if "NFCI" in indicator_name:
        mu, std = get_adaptive_anchor(data_series, 0.0, 0.50)
        base_z = (mu - current_val) / std
    elif "HY OAS" in indicator_name or "Kredi" in indicator_name:
        mu, std = get_adaptive_anchor(data_series, 4.20, 1.50)
        if "Güvenli Liman" in indicator_name:
            base_z = (current_val - mu) / std
        else:
            base_z = (mu - current_val) / std
    elif "VIX" in indicator_name:
        mu, std = get_adaptive_anchor(data_series, 19.5, 6.0)
        base_z = (mu - current_val) / std
    elif "MOVE" in indicator_name:
        mu, std = get_adaptive_anchor(data_series, 90.0, 25.0)
        base_z = (mu - current_val) / std
    elif "10Y Breakeven" in indicator_name or "5y5y" in indicator_name.lower():
        mu, std = get_adaptive_anchor(data_series, 2.20, 0.35)
        base_z = (current_val - mu) / std
        if invert:
            base_z = -base_z
    elif "Reel Faiz" in indicator_name:
        mu, std = get_adaptive_anchor(data_series, 1.25, 0.80)
        base_z = (mu - current_val) / std 
        if invert:
            base_z = -base_z
    elif "Piyasa Faiz İndirim Makası" in indicator_name:
        base_z = (current_val - 0.0) / 0.80
    elif "USD/JPY" in indicator_name or "Yen Carry" in indicator_name:
        if current_val > 155.0:
            base_z = 0.50 - ((current_val - 155.0) / 8.0)
        elif current_val < 135.0:
            base_z = (current_val - 135.0) / 15.0
        else:
            base_z = (current_val - 135.0) / 20.0
    elif "Stablecoin" in indicator_name:
        pct_90 = (data_series.pct_change(90).dropna().iloc[-1]) * 100 if len(data_series) > 90 else 5.0
        base_z = (pct_90 - 2.0) / 4.0
    elif "Korku & Açgözlülük" in indicator_name:
        if current_val >= 75.0:
            base_z = 0.50 - ((current_val - 75.0) / 25.0)
        elif current_val <= 25.0:
            base_z = (25.0 - current_val) / 20.0
        else:
            base_z = (current_val - 45.0) / 20.0
    elif "G4 Küresel Süper Likidite" in indicator_name:
        diff_60 = data_series.diff(60).dropna()
        std_60 = diff_60.std() if len(diff_60) > 10 else 1.0
        base_z = (diff_60.iloc[-1]) / (std_60 + 1e-5)
    elif "Altın / Gümüş Değerleme Rasyosu" in indicator_name:
        base_z = (current_val - 80.0) / 10.0
    elif "ABD Kamu Borcu" in indicator_name:
        pct_yoy = (data_series.pct_change(252).dropna().iloc[-1]) * 100 if len(data_series) > 252 else 5.0
        base_z = (pct_yoy - 4.0) / 3.0
    else:
        lookback = min(len(data_series), 252)
        ema_trend = data_series.ewm(span=40, adjust=False).mean().iloc[-1]
        mean_baseline = data_series.tail(lookback).mean()
        std_baseline = data_series.tail(lookback).std()
        base_z = (ema_trend - mean_baseline) / (std_baseline + 1e-5)
        if invert:
            base_z = -base_z
            
    z_score = float(max(-2.5, min(2.5, base_z)))
    return z_score, current_val


def safe_spread(s1: pd.Series, s2: pd.Series) -> pd.Series:
    if s1 is None or s2 is None or s1.empty or s2.empty:
        return pd.Series(dtype=float)
    df = pd.concat([s1, s2], axis=1).ffill().dropna()
    if df.empty or len(df.columns) < 2:
        return pd.Series(dtype=float)
    return (df.iloc[:, 0] - df.iloc[:, 1]).dropna()


def build_g4_net_liquidity(walcl, tga, rrp, ecb=None, eurusd=None, boj=None, usdjpy=None) -> pd.Series:
    """Same construction app.py used: US net liquidity + ECB (EUR->USD, x0.35)
    + BoJ (JPY->USD, x0.25). Falls back to US-only when the others are missing."""
    from macro_event_interpretation import compute_net_liquidity
    try:
        parts = [compute_net_liquidity(walcl, tga, rrp).rename("us_net")]
        if ecb is not None and eurusd is not None and not ecb.empty and not eurusd.empty:
            d = pd.concat([ecb, eurusd], axis=1).sort_index().ffill().dropna()
            if not d.empty:
                parts.append((d.iloc[:, 0] * d.iloc[:, 1] * 0.35).rename("ecb_usd"))
        if boj is not None and usdjpy is not None and not boj.empty and not usdjpy.empty:
            d = pd.concat([boj, usdjpy], axis=1).sort_index().ffill().dropna()
            if not d.empty:
                parts.append(((d.iloc[:, 0] * 100.0 / (d.iloc[:, 1] + 1e-8)) * 0.25).rename("boj_usd"))
        df = pd.concat(parts, axis=1).sort_index().ffill().dropna()
        return df.sum(axis=1).dropna().astype(float)
    except Exception:
        return compute_net_liquidity(walcl, tga, rrp)


# (indicator name, series key in the input map, invert flag)
# Series keys: dxy, g4_liq, dfii10, t10yie, t5yifr, fed_easing_spread, hy_oas,
#              move, vix, t10y2y, icsa, wresbal
INDICATOR_SPECS = (
    ("Dolar Endeksi Zayıflığı (DXY)", "dxy", True),
    ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", "g4_liq", False),
    # FIX: was True -> double inversion (see module docstring)
    ("Reel Faiz İndirgeme İvmesi (10Y TIPS)", "dfii10", False),
    ("10Y Breakeven Enflasyon İvmesi", "t10yie", False),
    ("5Y5Y İleri Enflasyon Beklentisi (T5YIFR)", "t5yifr", False),
    ("Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)", "fed_easing_spread", False),
    ("Yüksek Getirili Kredi Stresi (HY OAS)", "hy_oas", True),
    ("MOVE Endeksi (Tahvil Volatilitesi)", "move", True),
    ("VIX Endeksi (Hisse Volatilitesi)", "vix", True),
    ("Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)", "t10y2y", False),
    ("Öncü İstihdam (ICSA)", "icsa", True),
    ("Hazine Nakit / Banka Rezervleri (WRESBAL)", "wresbal", False),
)


def _slice(series: Optional[pd.Series], as_of=None) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    if as_of is None or series.empty:
        return series
    return series[series.index <= pd.Timestamp(as_of)]


REAL_YIELD_NAME = "Reel Faiz İndirgeme İvmesi (10Y TIPS)"
REAL_YIELD_VALUE_NAME = "Reel Faiz Seviyesi / Tahvil Taşıma Getirisi (TLT değerleme)"


def _real_yield_change_z(s: pd.Series, horizon: int = 60) -> float:
    """v2.6: the factor is named "İndirgeme İVMESİ" (easing MOMENTUM) but was
    computed as the LEVEL of real yields vs an anchor. Level and change mean
    different things: what hurts gold/Nasdaq/bonds is real yields RISING;
    a high but stable/falling level is not a headwind (for bonds it is the
    expected return). Now: z-score of the 60-business-day change, sign
    flipped so FALLING real yields = positive."""
    s = s.dropna()
    if len(s) < horizon + 60:
        return 0.0
    d = s.diff(horizon).dropna()
    hist = d.tail(756)
    sd = float(hist.std())
    if not np.isfinite(sd) or sd <= 1e-9:
        return 0.0
    # scaled by typical size of 60-day moves, NOT de-meaned: after a long
    # hiking cycle a flat real yield must read ~0, not 'easing'.
    sd = float(np.sqrt((hist ** 2).mean()))
    return float(np.clip(-d.iloc[-1] / max(sd, 1e-9), -2.5, 2.5))


def _real_yield_level_value_z(s: pd.Series) -> float:
    """Bond valuation/carry: a HIGH real yield means bonds are cheap and
    pay more (positive for TLT). Same adaptive anchor the old level logic
    used (50% theory 1.25%/0.80 + 50% trailing 5 years), sign = high -> +."""
    s = s.dropna()
    if len(s) < 30:
        return 0.0
    mu, sd = get_adaptive_anchor(s, 1.25, 0.80)
    return float(np.clip((float(s.iloc[-1]) - mu) / max(sd, 1e-6), -2.5, 2.5))


def compute_factor_scores(series_map: Dict[str, pd.Series], as_of=None) -> Dict[str, Dict[str, float]]:
    """Returns {indicator: {"z": score, "value": current}} using only data up to ``as_of``."""
    out = {}
    for name, key, invert in INDICATOR_SPECS:
        series = _slice(series_map.get(key), as_of)
        z, val = process_indicator(series, name, invert)
        if name == REAL_YIELD_NAME:
            z = _real_yield_change_z(series)
            out[REAL_YIELD_VALUE_NAME] = {"z": _real_yield_level_value_z(series), "value": float(val)}
        out[name] = {"z": float(z), "value": float(val)}
    return out


# Asset-specific extra factors (weight = share of the asset's real-yield weight)
EXTRA_ASSET_FACTORS = {
    "ABD Tahvili / Faiz (TLT)": {REAL_YIELD_VALUE_NAME: 1.0},
}


def asset_factor_weights(asset: str, base_weights: Dict[str, float]) -> Dict[str, float]:
    w = dict(base_weights)
    for fac, share in EXTRA_ASSET_FACTORS.get(asset, {}).items():
        w[fac] = share * float(base_weights.get(REAL_YIELD_NAME, 0.1))
    tot = sum(w.values()) or 1.0
    return {k: v / tot for k, v in w.items()}


RELIABILITY_FILE = "validation_reports/signal_reliability.json"


def load_signal_reliability(path: str = RELIABILITY_FILE) -> Dict[str, Dict[str, float]]:
    """{asset: {"macro": r, "market": r, "structure": r}} written by the weekly
    real-data validation. Missing file -> {} (every component weight 1.0)."""
    import json
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh).get("assets", {})
        return {a: {c: float(v.get("reliability", 1.0)) for c, v in comps.items()} for a, comps in raw.items()}
    except Exception:
        return {}


def compute_all_asset_signals(
    factor_scores: Dict[str, float],
    asset_prices: Dict[str, pd.Series],
    structural_state: Dict[str, Any],
    confirmed_regime_id: int,
    subtype: str,
    regime_probs: Dict[str, float],
    in_transition: bool,
    as_of=None,
    use_reliability: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """Per-asset signal state exactly as the app's 8-asset scanner computes it."""
    from macro_event_interpretation import (
        compute_asset_signal_state,
        get_macro_interpretation_asset_multipliers,
    )
    from asset_regime_weights import ASSETS, get_dynamic_asset_weights

    mults = get_macro_interpretation_asset_multipliers(confirmed_regime_id, subtype)
    reliability = load_signal_reliability() if use_reliability else {}
    out = {}
    for asset in ASSETS:
        weights = asset_factor_weights(asset, get_dynamic_asset_weights(asset, confirmed_regime_id, regime_probs, in_transition))
        out[asset] = compute_asset_signal_state(
            asset, factor_scores, weights, _slice(asset_prices.get(asset), as_of),
            structural_state, confirmed_regime_id, mults.get(asset, 1.0),
            reliability=reliability.get(asset),
        )
    return out
