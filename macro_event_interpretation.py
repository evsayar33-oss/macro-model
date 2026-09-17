"""
🏛️ Macro Event Interpretation System v1.0
Module: macro-event-interpretation-system
Specification:
  - Principles:
      * mutual_exclusivity: true
      * active_regime_count: 1
      * normalization: 52_week_rolling_z_score (252 trading days)
      * hysteresis_confirmation_period_weeks: 2 (10 trading days)
      * scoring_type: deterministic
  - Priority Rules:
      * Category Priority: SHOCK_REGIMES (1, 2, 3, 4) > RISK_ON_REGIME (5)
      * Conflict Resolution: Highest absolute Z-score of main trigger indicator
      * Special Conflict Case (Regime 1 vs 3): IF T10YIE 52w_Z > +0.5 THEN Regime 1 ELSE Regime 3
      * Fallback Rule: IF no threshold is met THEN state = 'REJIMSIZ_GECIS' AND retain previous confirmed regime (hysteresis)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any


@dataclass
class RegimeThresholdConfig:
    """Configurable thresholds calibrated for dynamic tuning and backtest optimization."""
    # Rolling window parameters
    rolling_window_52w: int = 252
    min_periods_52w: int = 60
    hysteresis_period_days: int = 10     # 2-week hysteresis window (trading days)
    shock_confirmation_days: int = 4     # Standard confirmation for shock candidates
    risk_on_confirmation_days: int = 7   # Confirmation for structural liquidity rally
    extreme_shock_z: float = 2.50        # Rare multi-factor shock fast-track threshold
    extreme_shock_confirmation_days: int = 1
    
    # Regime 1: Küresel Enflasyon & Stagflasyon Şoku
    regime1_oil_z_thresh: float = 1.5
    regime1_bdi_z_thresh: float = -1.0
    regime1_hy_z_thresh: float = 0.5
    regime1_corr_thresh: float = 0.0
    
    # Regime 2: Sistemik Likidite Şoku & Carry Çöküşü
    regime2_dtwex_z_thresh: float = 1.0
    regime2_usdjpy_z_thresh: float = -2.0
    regime2_vix_z_thresh: float = 1.5
    regime2_basket_z_thresh: float = -1.5
    
    # Regime 3: Reel Faiz Şoku
    regime3_dfii10_z_thresh: float = 1.5
    regime3_t10yie_z_thresh: float = 0.5
    regime3_dxy_z_thresh: float = 0.35
    
    # Regime 4: Kredi Temerrüt Baskısı
    regime4_hy_z_thresh: float = 2.0
    regime4_hy_slope_thresh: float = 0.0
    regime4_ig_z_thresh: float = 1.0
    
    # Regime 5: Küresel Likidite Rallisi (Risk-On)
    regime5_hy_z_thresh: float = -0.5
    regime5_dtwex_z_min: float = -1.0
    regime5_dtwex_z_max: float = 0.5
    regime5_vol_percentile_thresh: float = 30.0
    regime5_ndl_z_thresh: float = 0.0
    
    # Special Conflict Case: Regime 1 vs Regime 3
    conflict_1_vs_3_t10yie_thresh: float = 0.5


def calc_rolling_zscore(series: pd.Series, window: int = 252, min_periods: int = 60) -> pd.Series:
    """Calculates 52-week rolling Z-score: (X - mean_52w) / std_52w."""
    if series.empty:
        return pd.Series(dtype=float)
    mean = series.rolling(window=window, min_periods=min_periods).mean()
    std = series.rolling(window=window, min_periods=min_periods).std()
    z = (series - mean) / (std.replace(0, np.nan) + 1e-8)
    return z.fillna(0.0)


def calc_rolling_slope(series: pd.Series, window: int = 10) -> pd.Series:
    """Fast analytical linear regression slope over rolling window."""
    if len(series) < window:
        return pd.Series(0.0, index=series.index)
    N = window
    x = np.arange(N)
    w = (x - x.mean()) / np.sum((x - x.mean()) ** 2)
    vals = series.values
    slopes = np.full(len(series), np.nan)
    for i in range(window - 1, len(series)):
        chunk = vals[i - window + 1 : i + 1]
        if not np.isnan(chunk).any():
            slopes[i] = np.dot(w, chunk)
    s = pd.Series(slopes, index=series.index).ffill().fillna(0.0)
    return s


def calc_rolling_percentile(series: pd.Series, window: int = 252, min_periods: int = 60) -> pd.Series:
    """Calculates rolling percentile rank (0 to 100)."""
    if series.empty:
        return pd.Series(dtype=float)
    pct = series.rolling(window=window, min_periods=min_periods).rank(pct=True) * 100.0
    return pct.fillna(50.0)


def calc_rolling_correlation(s1: pd.Series, s2: pd.Series, window: int = 60, min_periods: int = 20) -> pd.Series:
    """Calculates rolling correlation between two series."""
    df = pd.concat([s1, s2], axis=1).dropna()
    if df.empty or len(df.columns) < 2:
        return pd.Series(0.0, index=s1.index)
    corr = df.iloc[:, 0].rolling(window=window, min_periods=min_periods).corr(df.iloc[:, 1])
    corr = corr.reindex(s1.index).ffill().fillna(0.0)
    return corr


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Converts scalar-like values to finite float without leaking NaN/Inf into the model."""
    try:
        value = float(value)
        return value if np.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _sigmoid01(x: float, scale: float = 1.0) -> float:
    """Stable 0..1 sigmoid used by the continuous regime layer."""
    scale = max(float(scale), 1e-6)
    return float(1.0 / (1.0 + np.exp(-np.clip(float(x) / scale, -12.0, 12.0))))


def _softmax(scores: Dict[str, float], temperature: float = 1.0) -> Dict[str, float]:
    """Numerically stable softmax over regime logits."""
    t = max(float(temperature), 1e-6)
    keys = list(scores.keys())
    vals = np.asarray([_safe_float(scores[k]) / t for k in keys], dtype=float)
    vals -= np.max(vals)
    exps = np.exp(np.clip(vals, -50.0, 50.0))
    denom = float(exps.sum()) or 1.0
    return {k: float(v / denom) for k, v in zip(keys, exps)}


def compute_continuum_regime_state(
    row: Optional[pd.Series],
    confirmed_regime_id: int = 0,
    candidate_regime_id: int = 0,
    in_transition: bool = False,
) -> Dict[str, Any]:
    """
    Event-aware continuous regime classifier.

    Unlike the old Continuum implementation, this layer consumes the same
    normalized feature row as the deterministic engine, so commodity shocks,
    real-rate shocks, credit stress, liquidity and volatility cannot silently
    bypass the active regime calculation.
    """
    if row is None or len(row) == 0:
        return {
            'dominant_regime': 'GOLDILOCKS',
            'regime_title': 'GOLDILOCKS (%100 - Varsayılan)',
            'blended_multiplier': 1.00,
            'inflation_anchor': 0.0,
            'regime_probs': {'GOLDILOCKS': 1.0, 'REFLASYON': 0.0, 'STAGFLASYON': 0.0, 'DEFLASYON': 0.0},
            'diagnostics': {},
        }

    get = lambda key, default=0.0: _safe_float(row.get(key, default), default)

    # Core continuous state variables, all dimensionless or percentile-normalized.
    inflation = _sigmoid01(get('t10yie_z') - 0.10, 0.65)
    commodity = _sigmoid01(max(get('commodity_impulse_z'), get('oil_ret20_z'), 0.80 * get('oil_ret5_z')) - 0.10, 0.70)
    real_rate = _sigmoid01(get('dfii10_chg1_z') - 0.35, 0.70)
    dollar_pressure = _sigmoid01(get('dxy_chg5_z') + get('dxy_level_z') * 0.35, 0.85)
    credit_stress = _sigmoid01((0.70 * get('hy_oas_z') + 0.30 * get('ig_oas_z')) - 0.15, 0.85)
    equity_stress = _sigmoid01(get('vix_level_z') - 0.35, 0.85)
    bond_stress = _sigmoid01(get('move_pctl252') / 25.0 - 2.0, 0.90)
    risk_asset_stress = _sigmoid01(-get('basket_ret5d_z') - 0.20, 0.90)
    financial_conditions_stress = _sigmoid01(get('nfci_z') - 0.10, 0.80)
    liquidity = _sigmoid01(get('ndl_z'), 0.80)
    employment_health = _sigmoid01(-get('icsa_level_z'), 0.80)
    trade_growth = _sigmoid01(get('bdi_level_z'), 1.00)

    systemic_stress = float(np.clip(
        0.32 * credit_stress
        + 0.24 * equity_stress
        + 0.16 * bond_stress
        + 0.14 * risk_asset_stress
        + 0.10 * financial_conditions_stress
        + 0.06 * (1.0 - liquidity),
        0.0, 1.0
    ))
    growth = float(np.clip(
        0.45 * employment_health + 0.35 * trade_growth + 0.20 * liquidity,
        0.0, 1.0
    ))

    # Regime logits: these encode relationships, not hard boundaries.
    logits = {
        'GOLDILOCKS': (
            1.80 * growth
            + 1.35 * liquidity
            + 0.90 * (1.0 - systemic_stress)
            - 0.90 * inflation
            - 0.65 * commodity
            - 0.55 * real_rate
        ),
        'REFLASYON': (
            1.30 * commodity
            + 1.10 * inflation
            + 0.90 * liquidity
            + 0.45 * growth
            - 0.85 * systemic_stress
            - 0.35 * real_rate
        ),
        'STAGFLASYON': (
            1.55 * commodity
            + 1.25 * inflation
            + 1.25 * systemic_stress
            + 0.65 * real_rate
            + 0.35 * dollar_pressure
            - 0.90 * growth
            - 0.45 * liquidity
        ),
        'DEFLASYON': (
            1.65 * systemic_stress
            + 1.10 * real_rate
            + 0.55 * dollar_pressure
            + 0.55 * (1.0 - liquidity)
            - 1.05 * inflation
            - 0.80 * commodity
            - 0.75 * growth
        ),
    }

    # Deterministic event bridge: the continuous layer must react to the same
    # confirmed/candidate event instead of working as an unrelated model.
    regime_overlay = {k: 0.0 for k in logits}
    overlays = {
        1: {'STAGFLASYON': 2.20, 'REFLASYON': 0.85},
        2: {'DEFLASYON': 2.30, 'STAGFLASYON': 0.55},
        3: {'DEFLASYON': 1.55, 'STAGFLASYON': 0.95},
        4: {'DEFLASYON': 2.35, 'STAGFLASYON': 0.55},
        5: {'GOLDILOCKS': 1.25, 'REFLASYON': 0.95},
    }

    if confirmed_regime_id in overlays:
        for key, value in overlays[confirmed_regime_id].items():
            regime_overlay[key] += value

    # Candidate shock/rally gets a smaller boost while hysteresis is pending.
    if in_transition and candidate_regime_id in overlays and candidate_regime_id != confirmed_regime_id:
        transition_strength = 0.55 if candidate_regime_id in (1, 2, 3, 4) else 0.35
        for key, value in overlays[candidate_regime_id].items():
            regime_overlay[key] += value * transition_strength

    adjusted_logits = {k: logits[k] + regime_overlay[k] for k in logits}
    probs = _softmax(adjusted_logits, temperature=0.55)

    # Explicit rare-event guardrails. If a very strong commodity/inflation
    # shock or systemic shock is present, do not allow the softmax to hide it.
    commodity_event = max(get('commodity_impulse_z'), get('oil_ret20_z'), 0.80 * get('oil_ret5_z'))
    real_rate_event = get('dfii10_chg1_z')
    stress_event = max(get('vix_level_z'), get('hy_oas_z'), get('ig_oas_z'))

    if commodity_event >= 2.20 and inflation >= 0.62:
        probs = {k: float(v) * 0.55 for k, v in probs.items()}
        probs['STAGFLASYON'] += 0.28
        probs['REFLASYON'] += 0.17
    elif commodity_event >= 1.80:
        probs = {k: float(v) * 0.70 for k, v in probs.items()}
        probs['REFLASYON'] += 0.18
        probs['STAGFLASYON'] += 0.12

    if real_rate_event >= 2.20 and get('dxy_chg5_z') > 0.20:
        probs = {k: float(v) * 0.70 for k, v in probs.items()}
        probs['DEFLASYON'] += 0.20
        if inflation > 0.55:
            probs['STAGFLASYON'] += 0.12

    if stress_event >= 2.50 and systemic_stress >= 0.65:
        probs = {k: float(v) * 0.65 for k, v in probs.items()}
        probs['DEFLASYON'] += 0.25
        probs['STAGFLASYON'] += 0.10

    total = sum(probs.values()) or 1.0
    probs = {k: float(v / total) for k, v in probs.items()}
    dominant_regime = max(probs, key=probs.get)
    dom_pct = int(round(probs[dominant_regime] * 100.0))

    base_multipliers = {
        'GOLDILOCKS': 1.10,
        'REFLASYON': 1.18,
        'STAGFLASYON': 1.35,
        'DEFLASYON': 0.82,
    }
    blended_multiplier = float(sum(probs[k] * base_multipliers[k] for k in base_multipliers))
    inf_anchor = get('t10yie_level', 0.0)
    title_map = {
        'GOLDILOCKS': f'GOLDILOCKS (%{dom_pct} - Büyüme/Likidite Dengesi)',
        'REFLASYON': f'REFLASYON (%{dom_pct} - Emtia/Enflasyon + Likidite)',
        'STAGFLASYON': f'STAGFLASYON (%{dom_pct} - Emtia/Enflasyon + Stres)',
        'DEFLASYON': f'DEFLASYONİST DARALMA (%{dom_pct} - Stres/Sıkı Finansal Koşullar)',
    }

    return {
        'dominant_regime': dominant_regime,
        'regime_title': title_map[dominant_regime],
        'blended_multiplier': blended_multiplier,
        'inflation_anchor': inf_anchor,
        'regime_probs': probs,
        'diagnostics': {
            'inflation_pressure': inflation,
            'commodity_pressure': commodity,
            'real_rate_pressure': real_rate,
            'systemic_stress': systemic_stress,
            'growth_health': growth,
            'liquidity_health': liquidity,
            'commodity_event_z': commodity_event,
            'real_rate_event_z': real_rate_event,
            'stress_event_z': stress_event,
        },
    }


class MacroEventInterpretationSystem:
    """
    Deterministic Macro Event Interpretation Engine v1.0.
    Evaluates 5 macro regimes, conflict resolution, sub-type tagging, and hysteresis.
    """
    def __init__(self, config: Optional[RegimeThresholdConfig] = None):
        self.config = config or RegimeThresholdConfig()
        
    def compute_indicators(self, data: Dict[str, pd.Series]) -> pd.DataFrame:
        """
        Computes all normalized indicators and features required by the 5 regimes.
        """
        cfg = self.config
        
        # Build common aligned index across all series
        df = pd.DataFrame(data).sort_index().ffill().dropna(how='all')
        features = pd.DataFrame(index=df.index)
        
        # 1. Regime 1 Indicators
        if 'oil' in df:
            ret_5d = df['oil'].pct_change(5)
            ret_20d = df['oil'].pct_change(20)
            features['oil_ret5_z'] = calc_rolling_zscore(ret_5d, cfg.rolling_window_52w, cfg.min_periods_52w)
            features['oil_ret20_z'] = calc_rolling_zscore(ret_20d, cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['oil_ret5_z'] = 0.0
            features['oil_ret20_z'] = 0.0

        # Broad commodity impulse prevents a single proxy (e.g. BDRY) from
        # vetoing a genuine commodity inflation shock.
        commodity_return_zs = []
        for commodity_key in ('oil', 'gold', 'xag', 'hg', 'dbb'):
            if commodity_key in df:
                ret = df[commodity_key].pct_change(20)
                z = calc_rolling_zscore(ret, cfg.rolling_window_52w, cfg.min_periods_52w)
                features[f'{commodity_key}_ret20_z'] = z
                commodity_return_zs.append(z)
        if commodity_return_zs:
            commodity_frame = pd.concat(commodity_return_zs, axis=1)
            features['commodity_impulse_z'] = commodity_frame.mean(axis=1, skipna=True).fillna(features['oil_ret20_z'])
            features['commodity_breadth'] = (commodity_frame > 0.5).sum(axis=1).astype(float) / max(commodity_frame.shape[1], 1)
        else:
            features['commodity_impulse_z'] = features['oil_ret20_z']
            features['commodity_breadth'] = 0.0
            
        if 'bdi' in df:
            features['bdi_level_z'] = calc_rolling_zscore(df['bdi'], cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['bdi_level_z'] = 0.0
            
        if 'hy_oas' in df:
            features['hy_oas_z'] = calc_rolling_zscore(df['hy_oas'], cfg.rolling_window_52w, cfg.min_periods_52w)
            features['hy_oas_slope10'] = calc_rolling_slope(df['hy_oas'], window=10)
        else:
            features['hy_oas_z'] = 0.0
            features['hy_oas_slope10'] = 0.0
            
        if 'spx' in df and 'ust10y' in df:
            ret_spx = df['spx'].pct_change()
            # If ust10y is yield (< 25), convert yield change to bond return:
            if df['ust10y'].mean() < 25.0:
                ret_ust10 = -df['ust10y'].diff() * 8.0
            else:
                ret_ust10 = df['ust10y'].pct_change()
            features['spx_ust10_corr60'] = calc_rolling_correlation(ret_spx, ret_ust10, window=60)
        else:
            features['spx_ust10_corr60'] = 0.0
            
        # 2. Regime 2 Indicators
        if 'dtwex' in df:
            chg5_dtwex = df['dtwex'].diff(5)
            features['dtwex_chg5_z'] = calc_rolling_zscore(chg5_dtwex, cfg.rolling_window_52w, cfg.min_periods_52w)
            features['dtwex_level_z'] = calc_rolling_zscore(df['dtwex'], cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['dtwex_chg5_z'] = 0.0
            features['dtwex_level_z'] = 0.0
            
        if 'usdjpy' in df:
            chg1_usdjpy = df['usdjpy'].diff(1)
            features['usdjpy_chg1_z'] = calc_rolling_zscore(chg1_usdjpy, cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['usdjpy_chg1_z'] = 0.0
            
        if 'vix' in df:
            features['vix_level_z'] = calc_rolling_zscore(df['vix'], cfg.rolling_window_52w, cfg.min_periods_52w)
            features['vix_pctl252'] = calc_rolling_percentile(df['vix'], cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['vix_level_z'] = 0.0
            features['vix_pctl252'] = 50.0
            
        if 'move' in df:
            features['move_pctl252'] = calc_rolling_percentile(df['move'], cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['move_pctl252'] = features.get('vix_pctl252', 50.0)
            
        # Equal-weighted basket (BTC + SPX) 5-day return
        if 'btc' in df and 'spx' in df:
            ret_btc_5d = df['btc'].pct_change(5)
            ret_spx_5d = df['spx'].pct_change(5)
            basket_ret5d = 0.5 * ret_btc_5d + 0.5 * ret_spx_5d
            features['basket_ret5d_z'] = calc_rolling_zscore(basket_ret5d, cfg.rolling_window_52w, cfg.min_periods_52w)
        elif 'spx' in df:
            ret_spx_5d = df['spx'].pct_change(5)
            features['basket_ret5d_z'] = calc_rolling_zscore(ret_spx_5d, cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['basket_ret5d_z'] = 0.0
            
        # 3. Regime 3 Indicators
        if 'dfii10' in df:
            chg1_dfii10 = df['dfii10'].diff(1)
            features['dfii10_chg1_z'] = calc_rolling_zscore(chg1_dfii10, cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['dfii10_chg1_z'] = 0.0

        # DXY Indicator for Regime 3
        if 'dxy' in df:
            features['dxy_level_z'] = calc_rolling_zscore(df['dxy'], cfg.rolling_window_52w, cfg.min_periods_52w)
            features['dxy_chg5_z'] = calc_rolling_zscore(df['dxy'].diff(5), cfg.rolling_window_52w, cfg.min_periods_52w)
        elif 'dtwex' in df:
            features['dxy_level_z'] = features.get('dtwex_level_z', calc_rolling_zscore(df['dtwex'], cfg.rolling_window_52w, cfg.min_periods_52w))
            features['dxy_chg5_z'] = features.get('dtwex_chg5_z', calc_rolling_zscore(df['dtwex'].diff(5), cfg.rolling_window_52w, cfg.min_periods_52w))
        else:
            features['dxy_level_z'] = 0.0
            features['dxy_chg5_z'] = 0.0
            
        if 't10yie' in df:
            features['t10yie_z'] = calc_rolling_zscore(df['t10yie'], cfg.rolling_window_52w, cfg.min_periods_52w)
            features['t10yie_level'] = df['t10yie']
        else:
            features['t10yie_z'] = 0.0
            features['t10yie_level'] = 0.0

        if 'nfci' in df:
            features['nfci_z'] = calc_rolling_zscore(df['nfci'], cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['nfci_z'] = 0.0
            
        if 'ust2y' in df and 'ust10y' in df:
            features['delta_dgs2'] = df['ust2y'].diff(5)
            features['delta_dgs10'] = df['ust10y'].diff(5)
        else:
            features['delta_dgs2'] = 0.0
            features['delta_dgs10'] = 0.0
            
        # 4. Regime 4 Indicators
        if 'ig_oas' in df:
            features['ig_oas_z'] = calc_rolling_zscore(df['ig_oas'], cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['ig_oas_z'] = features['hy_oas_z'] * 0.8
            
        # 5. Regime 5 Indicators
        if 'ndl' in df:
            features['ndl_z'] = calc_rolling_zscore(df['ndl'], cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['ndl_z'] = 0.0

        if 'icsa' in df:
            features['icsa_level_z'] = calc_rolling_zscore(df['icsa'], cfg.rolling_window_52w, cfg.min_periods_52w)
            features['icsa_chg4w_z'] = calc_rolling_zscore(df['icsa'].diff(20), cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['icsa_level_z'] = 0.0
            features['icsa_chg4w_z'] = 0.0
            
        if 'gold' in df:
            features['gold_ret20'] = df['gold'].pct_change(20)
        else:
            features['gold_ret20'] = 0.0
            
        return features

    def evaluate_row(self, row: pd.Series) -> Dict[str, Any]:
        """
        Evaluates five mutually exclusive macro regimes using multi-factor evidence.

        The key design change is that a commodity shock is no longer vetoed by a
        single BDI proxy, while conflict arbitration uses regime strength rather
        than one raw indicator.
        """
        cfg = self.config
        get = lambda key, default=0.0: _safe_float(row.get(key, default), default)

        # --- REGIME 1: GLOBAL INFLATION / STAGFLATION SHOCK ---
        oil_z = get('oil_ret20_z')
        oil_fast_z = get('oil_ret5_z')
        commodity_z = max(get('commodity_impulse_z'), oil_z, 0.80 * oil_fast_z)
        inflation_z = get('t10yie_z')
        hy_z = get('hy_oas_z')
        bdi_z = get('bdi_level_z')
        corr = get('spx_ust10_corr60')
        ig_z = get('ig_oas_z')
        commodity_breadth = get('commodity_breadth')

        # A genuine commodity supply/cost shock must not wait for BDI or credit
        # markets to confirm it. Broad cross-commodity participation acts as an
        # independent support channel and is especially important at shock onset.
        broad_commodity_event = commodity_z > 1.80 and commodity_breadth >= 0.60
        r1_t1 = (oil_z > cfg.regime1_oil_z_thresh) or (commodity_z > 1.30)
        r1_t2 = (inflation_z > 0.25) or (bdi_z < -0.75) or broad_commodity_event
        r1_c1 = (hy_z > 0.25) or (ig_z > 0.25)
        r1_c2 = (corr > -0.25) or broad_commodity_event
        r1_support_count = int(r1_t2) + int(r1_c1) + int(r1_c2)
        r1_active = r1_t1 and r1_support_count >= 2
        r1_main_z = max(oil_z, commodity_z, inflation_z, max(hy_z, 0.0))
        r1_strength = float(np.clip(
            0.45 * max(commodity_z, 0.0)
            + 0.25 * max(inflation_z, 0.0)
            + 0.18 * max(hy_z, 0.0)
            + 0.12 * max(-bdi_z, 0.0),
            0.0, 5.0
        ))
        if commodity_z > 1.50 and inflation_z > 0.50:
            r1_subtype = 'Emtia-Enflasyon Şoku'
        elif inflation_z > 0.50:
            r1_subtype = 'Yapışkan Enflasyon / Maliyet Şoku'
        else:
            r1_subtype = 'Emtia Maliyet Baskısı'

        # --- REGIME 2: SYSTEMIC LIQUIDITY / CARRY SHOCK ---
        dtwex_chg_z = get('dtwex_chg5_z')
        usdjpy_chg_z = get('usdjpy_chg1_z')
        vix_z = get('vix_level_z')
        basket_z = get('basket_ret5d_z')
        move_pctl = get('move_pctl252', 50.0)
        r2_t1 = dtwex_chg_z > cfg.regime2_dtwex_z_thresh
        r2_t2 = usdjpy_chg_z < cfg.regime2_usdjpy_z_thresh
        r2_t3 = vix_z > cfg.regime2_vix_z_thresh
        r2_t4 = move_pctl > 95.0
        r2_trigger_count = int(r2_t1) + int(r2_t2) + int(r2_t3) + int(r2_t4)
        r2_triggers_met = r2_trigger_count >= 1
        r2_c1 = basket_z < cfg.regime2_basket_z_thresh
        # A very strong volatility/carry event can stand on its own; otherwise
        # require the risk-asset confirmation to avoid false systemic labels.
        r2_confirms_met = r2_c1 or ((r2_t2 or r2_t3 or r2_t4) and basket_z < -0.75)
        r2_active = r2_triggers_met and r2_confirms_met
        r2_main_z = max(
            abs(dtwex_chg_z) if r2_t1 else 0.0,
            abs(usdjpy_chg_z) if r2_t2 else 0.0,
            abs(vix_z) if r2_t3 else 0.0,
            2.0 if r2_t4 else 0.0,
        )
        r2_strength = float(np.clip(
            0.35 * max(abs(usdjpy_chg_z), 0.0)
            + 0.30 * max(vix_z, 0.0)
            + 0.20 * max(-basket_z, 0.0)
            + 0.10 * max(dtwex_chg_z, 0.0)
            + 0.05 * max((move_pctl - 80.0) / 10.0, 0.0),
            0.0, 5.0
        ))

        # --- REGIME 3: REAL RATE SHOCK ---
        dfii_z = get('dfii10_chg1_z')
        dxy_level_z = get('dxy_level_z')
        dxy_chg5_z = get('dxy_chg5_z')
        r3_t1 = dfii_z > cfg.regime3_dfii10_z_thresh
        r3_t2 = inflation_z < cfg.regime3_t10yie_z_thresh
        r3_t3 = dxy_level_z > cfg.regime3_dxy_z_thresh or dxy_chg5_z > 0.50
        r3_triggers_met = r3_t1 and r3_t2 and r3_t3
        r3_active = r3_triggers_met
        r3_main_z = max(abs(dfii_z), abs(dxy_level_z), abs(dxy_chg5_z))
        r3_strength = float(np.clip(
            0.50 * max(dfii_z, 0.0)
            + 0.25 * max(dxy_level_z, dxy_chg5_z, 0.0)
            + 0.15 * max(-inflation_z, 0.0)
            + 0.10 * max(get('move_pctl252') - 70.0, 0.0) / 10.0,
            0.0, 5.0
        ))

        d2 = get('delta_dgs2')
        d10 = get('delta_dgs10')
        if d2 < 0 and d10 > 0:
            r3_subtype = 'Bear Steepener (Enflasyon/Term Premium)'
        elif d2 > 0 and d10 > 0 and d10 > d2:
            r3_subtype = 'Bear Steepener (Fed Varyantı)'
        elif d2 > 0 and d10 > 0 and d2 > d10:
            r3_subtype = 'Bear Flattener (Fed Sıkılaştırma Baskın)'
        elif d2 < 0 and d10 < 0:
            r3_subtype = 'Bull Flattener/Steepener (Gevşeme - Tetiklemez)'
        else:
            r3_subtype = 'Dengeli / Nötr Eğri'

        # --- REGIME 4: CREDIT DEFAULT / SPREAD STRESS ---
        hy_slope = get('hy_oas_slope10')
        r4_t1 = hy_z > cfg.regime4_hy_z_thresh
        r4_t2 = hy_slope > cfg.regime4_hy_slope_thresh
        r4_triggers_met = r4_t1 and r4_t2
        r4_c1 = ig_z > cfg.regime4_ig_z_thresh
        r4_confirms_met = r4_c1 or (hy_z > 2.50 and vix_z > 1.00)
        r4_active = r4_triggers_met and r4_confirms_met
        r4_main_z = abs(hy_z)
        r4_strength = float(np.clip(
            0.55 * max(hy_z, 0.0)
            + 0.25 * max(ig_z, 0.0)
            + 0.10 * max(vix_z, 0.0)
            + 0.10 * max(hy_slope, 0.0),
            0.0, 5.0
        ))

        # --- REGIME 5: GLOBAL LIQUIDITY RALLY / RISK-ON ---
        ndl_z = get('ndl_z')
        min_vol_pctl = min(get('vix_pctl252', 50.0), get('move_pctl252', 50.0))
        r5_t1 = hy_z < cfg.regime5_hy_z_thresh
        r5_t2 = cfg.regime5_dtwex_z_min <= get('dtwex_level_z') <= cfg.regime5_dtwex_z_max
        r5_t3 = min_vol_pctl < cfg.regime5_vol_percentile_thresh
        r5_t4 = ndl_z > cfg.regime5_ndl_z_thresh
        r5_triggers_met = r5_t1 and r5_t2 and r5_t3 and r5_t4
        r5_active = r5_triggers_met
        r5_strength = float(np.clip(
            0.35 * max(-hy_z, 0.0)
            + 0.30 * max(ndl_z, 0.0)
            + 0.20 * max(-get('dxy_level_z'), 0.0)
            + 0.15 * max((30.0 - min_vol_pctl) / 10.0, 0.0),
            0.0, 5.0
        ))

        gold_ret = get('gold_ret20')
        dtwex_z = get('dtwex_level_z')
        if dtwex_z < -0.5 and gold_ret > 0:
            r5_subtype = 'Reflasyonist Risk-On'
        elif (-1.0 <= dtwex_z <= 0.5) and gold_ret <= 0:
            r5_subtype = 'Klasik Goldilocks Risk-On'
        else:
            r5_subtype = 'Dengeli Likidite Rallisi'

        # --- PRIORITY & CONFLICT RESOLUTION ---
        active_shocks = []
        if r1_active:
            active_shocks.append((1, r1_strength, r1_main_z))
        if r2_active:
            active_shocks.append((2, r2_strength, r2_main_z))
        if r3_active:
            active_shocks.append((3, r3_strength, r3_main_z))
        if r4_active:
            active_shocks.append((4, r4_strength, r4_main_z))

        candidate_regime_id = 0
        conflict_note = 'Yok'
        active_subtype = 'N/A'

        if active_shocks:
            if len(active_shocks) == 1:
                candidate_regime_id = active_shocks[0][0]
            else:
                shock_ids = [s[0] for s in active_shocks]
                if set(shock_ids) == {1, 3}:
                    # Keep the historical T10YIE split as a tie-breaker, but
                    # first compare multivariate event strength.
                    r1_strength_val = r1_strength
                    r3_strength_val = r3_strength
                    if abs(r1_strength_val - r3_strength_val) < 0.15:
                        candidate_regime_id = 1 if inflation_z > cfg.conflict_1_vs_3_t10yie_thresh else 3
                        conflict_note = (
                            f'R1 vs R3 güç yakınlığı -> T10YIE_Z ({inflation_z:.2f}) ' 
                            f"{'>' if inflation_z > cfg.conflict_1_vs_3_t10yie_thresh else '<='} +0.5 ayrıştırıcısı => Rejim {candidate_regime_id}"
                        )
                    else:
                        candidate_regime_id = 1 if r1_strength_val > r3_strength_val else 3
                        conflict_note = (
                            f'Çoklu Şok {shock_ids}: Çok faktörlü güç karşılaştırması ' 
                            f'R1={r1_strength_val:.2f}, R3={r3_strength_val:.2f} => Rejim {candidate_regime_id}'
                        )
                else:
                    best_shock = max(active_shocks, key=lambda x: (x[1], x[2]))
                    candidate_regime_id = best_shock[0]
                    conflict_note = (
                        f'Çoklu Şok Çözümü {shock_ids}: Çok faktörlü güç {best_shock[1]:.2f} ' 
                        f've ana Z {best_shock[2]:.2f} => Rejim {candidate_regime_id}'
                    )
        elif r5_active:
            candidate_regime_id = 5

        regime_names = {
            1: 'Küresel Enflasyon & Stagflasyon Şoku',
            2: 'Sistemik Likidite Şoku & Carry Çöküşü',
            3: 'Reel Faiz Şoku',
            4: 'Kredi Temerrüt Baskısı',
            5: 'Küresel Likidite Rallisi (Risk-On)',
            0: 'REJIMSIZ_GECIS'
        }
        candidate_regime_name = regime_names.get(candidate_regime_id, 'REJIMSIZ_GECIS')

        if candidate_regime_id == 1:
            active_subtype = r1_subtype
        elif candidate_regime_id == 3:
            active_subtype = r3_subtype
        elif candidate_regime_id == 5:
            active_subtype = r5_subtype

        # Fast-track only truly extraordinary events; ordinary candidates keep
        # the standard hysteresis to avoid whipsaws.
        candidate_strength = {
            1: r1_strength, 2: r2_strength, 3: r3_strength, 4: r4_strength, 5: r5_strength, 0: 0.0
        }.get(candidate_regime_id, 0.0)
        max_event_z = max(
            abs(commodity_z), abs(dfii_z), abs(vix_z), abs(hy_z), abs(ig_z), abs(usdjpy_chg_z), abs(dtwex_chg_z)
        )
        extreme_event = bool(
            1 <= candidate_regime_id <= 4
            and max(max_event_z, candidate_strength) >= cfg.extreme_shock_z
            and (r1_support_count >= 2 if candidate_regime_id == 1 else True)
        )

        return {
            'candidate_id': candidate_regime_id,
            'candidate_name': candidate_regime_name,
            'subtype': active_subtype,
            'conflict_note': conflict_note,
            'extreme_event': extreme_event,
            'candidate_strength': float(candidate_strength),
            'r1_active': r1_active,
            'r2_active': r2_active,
            'r3_active': r3_active,
            'r4_active': r4_active,
            'r5_active': r5_active,
            'details': {
                'r1': {
                    't1': (float(oil_z), cfg.regime1_oil_z_thresh, bool(oil_z > cfg.regime1_oil_z_thresh)),
                    't2': (float(bdi_z), -0.75, bool(r1_t2)),
                    'c1': (float(hy_z), 0.25, bool(r1_c1)),
                    'c2': (float(corr), -0.25, bool(r1_c2)),
                    'commodity_z': float(commodity_z),
                    'commodity_breadth': float(commodity_breadth),
                    'broad_commodity_event': bool(broad_commodity_event),
                    'inflation_z': float(inflation_z),
                    'support_count': r1_support_count,
                    'subtype': r1_subtype,
                },
                'r2': {
                    't1': (float(dtwex_chg_z), cfg.regime2_dtwex_z_thresh, bool(r2_t1)),
                    't2': (float(usdjpy_chg_z), cfg.regime2_usdjpy_z_thresh, bool(r2_t2)),
                    't3': (float(vix_z), cfg.regime2_vix_z_thresh, bool(r2_t3)),
                    't4': (float(move_pctl), 95.0, bool(r2_t4)),
                    'c1': (float(basket_z), cfg.regime2_basket_z_thresh, bool(r2_c1)),
                },
                'r3': {
                    't1': (float(dfii_z), cfg.regime3_dfii10_z_thresh, bool(r3_t1)),
                    't2': (float(inflation_z), cfg.regime3_t10yie_z_thresh, bool(r3_t2)),
                    't3': (float(dxy_level_z), cfg.regime3_dxy_z_thresh, bool(r3_t3)),
                    'subtype': r3_subtype,
                },
                'r4': {
                    't1': (float(hy_z), cfg.regime4_hy_z_thresh, bool(r4_t1)),
                    't2': (float(hy_slope), cfg.regime4_hy_slope_thresh, bool(r4_t2)),
                    'c1': (float(ig_z), cfg.regime4_ig_z_thresh, bool(r4_c1)),
                },
                'r5': {
                    't1': (float(hy_z), cfg.regime5_hy_z_thresh, bool(r5_t1)),
                    't2': (float(dtwex_z), (cfg.regime5_dtwex_z_min, cfg.regime5_dtwex_z_max), bool(r5_t2)),
                    't3': (float(min_vol_pctl), cfg.regime5_vol_percentile_thresh, bool(r5_t3)),
                    't4': (float(ndl_z), cfg.regime5_ndl_z_thresh, bool(r5_t4)),
                    'subtype': r5_subtype,
                },
                'strengths': {
                    'R1': float(r1_strength), 'R2': float(r2_strength), 'R3': float(r3_strength),
                    'R4': float(r4_strength), 'R5': float(r5_strength),
                },
            }
        }

    def evaluate_history(self, data: Dict[str, pd.Series]) -> pd.DataFrame:
        """
        Runs historical evaluation applying the 2-week hysteresis state machine.
        """
        cfg = self.config
        features = self.compute_indicators(data)
        
        n = len(features)
        candidate_ids = np.zeros(n, dtype=int)
        confirmed_ids = np.zeros(n, dtype=int)
        subtypes = []
        conflict_notes = []
        in_transition = np.zeros(n, dtype=bool)
        
        current_confirmed = 0
        fallback_timer = 0
        cand_streak = 0
        active_cand = 0
        
        regime_names = {
            1: "Küresel Enflasyon & Stagflasyon Şoku",
            2: "Sistemik Likidite Şoku & Carry Çöküşü",
            3: "Reel Faiz Şoku",
            4: "Kredi Temerrüt Baskısı",
            5: "Küresel Likidite Rallisi (Risk-On)",
            0: "REJIMSIZ_GECIS"
        }
        
        for idx in range(n):
            row = features.iloc[idx]
            res = self.evaluate_row(row)
            c = res['candidate_id']
            candidate_ids[idx] = c
            subtypes.append(res['subtype'])
            conflict_notes.append(res['conflict_note'])
            
            # Hysteresis State Machine
            if c == 0:
                # Fallback rule: Retain previous confirmed regime for up to 10 trading days (2 weeks)
                if fallback_timer > 0 and current_confirmed != 0:
                    fallback_timer -= 1
                    confirmed_ids[idx] = current_confirmed
                    in_transition[idx] = True
                else:
                    current_confirmed = 0
                    fallback_timer = 0
                    confirmed_ids[idx] = 0
                    in_transition[idx] = False
                cand_streak = max(0, cand_streak - 1)
            else:
                if c == current_confirmed:
                    fallback_timer = cfg.hysteresis_period_days
                    confirmed_ids[idx] = current_confirmed
                    in_transition[idx] = False
                    cand_streak = cfg.hysteresis_period_days
                    active_cand = c
                else:
                    if c == active_cand:
                        cand_streak += 1
                    else:
                        active_cand = c
                        cand_streak = 1
                        
                    if 1 <= c <= 4 and res.get('extreme_event', False):
                        req = cfg.extreme_shock_confirmation_days
                    else:
                        req = cfg.shock_confirmation_days if (1 <= c <= 4) else cfg.risk_on_confirmation_days
                    if cand_streak >= req:
                        current_confirmed = c
                        fallback_timer = cfg.hysteresis_period_days
                        confirmed_ids[idx] = current_confirmed
                        in_transition[idx] = False
                    else:
                        confirmed_ids[idx] = current_confirmed
                        in_transition[idx] = True
                        
        result_df = features.copy()
        result_df['candidate_regime_id'] = candidate_ids
        result_df['candidate_regime_name'] = [regime_names[i] for i in candidate_ids]
        result_df['confirmed_regime_id'] = confirmed_ids
        result_df['confirmed_regime_name'] = [regime_names[i] for i in confirmed_ids]
        result_df['subtype'] = subtypes
        result_df['conflict_note'] = conflict_notes
        result_df['in_transition'] = in_transition
        
        return result_df


def get_macro_interpretation_asset_multipliers(confirmed_regime_id: int, subtype: str = "") -> Dict[str, float]:
    """
    Returns asset-specific exposure scaling multipliers based on the active deterministic regime.
    Protects capital in shocks and boosts exposure in risk-on.
    """
    if confirmed_regime_id == 1:
        # Küresel Enflasyon & Stagflasyon Şoku
        # Long Commodities/Gold, Cut Equities/Long Duration Bonds
        return {
            "Altın (XAU)": 1.25,
            "Gümüş (XAG)": 1.10,
            "Ham Petrol (WTI)": 1.35,
            "Bakır (HG)": 0.85,
            "S&P 500 (SPX)": 0.45,
            "Nasdaq 100 (NQ)": 0.40,
            "Kripto (BTC)": 0.35,
            "ABD Tahvili / Faiz (TLT)": 0.30
        }
    elif confirmed_regime_id == 2:
        # Sistemik Likidite Şoku & Carry Çöküşü
        # Flight to cash / defensive de-leveraging across all risk assets
        return {
            "Altın (XAU)": 0.80,
            "Gümüş (XAG)": 0.60,
            "Ham Petrol (WTI)": 0.50,
            "Bakır (HG)": 0.50,
            "S&P 500 (SPX)": 0.30,
            "Nasdaq 100 (NQ)": 0.25,
            "Kripto (BTC)": 0.20,
            "ABD Tahvili / Faiz (TLT)": 0.70
        }
    elif confirmed_regime_id == 3:
        # Reel Faiz Şoku
        # Real yields surging -> severe headwind for long-duration growth and precious metals
        if "Flattener" in subtype:
            tlt_mult = 0.40
        else:
            tlt_mult = 0.30
        return {
            "Altın (XAU)": 0.65,
            "Gümüş (XAG)": 0.60,
            "Ham Petrol (WTI)": 0.80,
            "Bakır (HG)": 0.75,
            "S&P 500 (SPX)": 0.50,
            "Nasdaq 100 (NQ)": 0.35,
            "Kripto (BTC)": 0.35,
            "ABD Tahvili / Faiz (TLT)": tlt_mult
        }
    elif confirmed_regime_id == 4:
        # Kredi Temerrüt Baskısı
        # Spreads widening -> cut credit & equities, safe-haven treasuries/gold
        return {
            "Altın (XAU)": 1.15,
            "Gümüş (XAG)": 0.85,
            "Ham Petrol (WTI)": 0.60,
            "Bakır (HG)": 0.55,
            "S&P 500 (SPX)": 0.35,
            "Nasdaq 100 (NQ)": 0.35,
            "Kripto (BTC)": 0.25,
            "ABD Tahvili / Faiz (TLT)": 1.20
        }
    elif confirmed_regime_id == 5:
        # Küresel Likidite Rallisi (Risk-On)
        if "Reflasyonist" in subtype:
            return {
                "Altın (XAU)": 1.30,
                "Gümüş (XAG)": 1.40,
                "Ham Petrol (WTI)": 1.20,
                "Bakır (HG)": 1.35,
                "S&P 500 (SPX)": 1.25,
                "Nasdaq 100 (NQ)": 1.30,
                "Kripto (BTC)": 1.45,
                "ABD Tahvili / Faiz (TLT)": 0.80
            }
        else:
            # Klasik Goldilocks
            return {
                "Altın (XAU)": 0.90,
                "Gümüş (XAG)": 1.05,
                "Ham Petrol (WTI)": 0.90,
                "Bakır (HG)": 1.10,
                "S&P 500 (SPX)": 1.35,
                "Nasdaq 100 (NQ)": 1.40,
                "Kripto (BTC)": 1.30,
                "ABD Tahvili / Faiz (TLT)": 1.10
            }
    else:
        # REJIMSIZ_GECIS: Neutral baseline multipliers
        return {k: 1.0 for k in [
            "Altın (XAU)", "Gümüş (XAG)", "Ham Petrol (WTI)", "Bakır (HG)",
            "S&P 500 (SPX)", "Nasdaq 100 (NQ)", "Kripto (BTC)", "ABD Tahvili / Faiz (TLT)"
        ]}


def render_macro_scorecard_ui(st_obj, eval_details: Dict[str, Any], confirmed_id: int, cand_id: int, subtype: str, in_trans: bool, conflict_note: str):
    """Renders the comprehensive 5-Regime Scorecard in Streamlit."""
    
    # Top Status Badges
    regime_badges = {
        1: ("🚨 ŞOK REJİMİ", "#ff4b4b", "Küresel Enflasyon & Stagflasyon Şoku"),
        2: ("🚨 ŞOK REJİMİ", "#ff4b4b", "Sistemik Likidite Şoku & Carry Çöküşü"),
        3: ("🚨 ŞOK REJİMİ", "#ffa500", "Reel Faiz Şoku"),
        4: ("🚨 ŞOK REJİMİ", "#ff4b4b", "Kredi Temerrüt Baskısı"),
        5: ("🟢 RİSK-ON REJİMİ", "#28a745", "Küresel Likidite Rallisi (Risk-On)"),
        0: ("⚪ REJİMSİZ GEÇİŞ", "#6c757d", "Nötr / Histerezis Korumalı Geçiş Dönemi")
    }
    
    badge_type, badge_color, badge_name = regime_badges.get(confirmed_id, regime_badges[0])
    
    st_obj.markdown(f"""
    <div style="background-color: #1e2130; padding: 18px; border-radius: 10px; border-left: 6px solid {badge_color}; margin-bottom: 20px;">
        <h3 style="margin: 0; color: white;">{badge_type}: {badge_name}</h3>
        <p style="margin: 5px 0 0 0; color: #d0d2d6; font-size: 15px;">
            <b>Alt-Tip (Sub-Type):</b> <span style="color: #61afef;">{subtype}</span> &nbsp;|&nbsp; 
            <b>Histerezis Durumu:</b> {'⏳ Geçiş Onayı Bekleniyor' if in_trans else '🔒 Kesinleşmiş (Onaylı)'} &nbsp;|&nbsp;
            <b>Ham Aday:</b> Rejim {cand_id} &nbsp;|&nbsp;
            <b>Çatışma Çözümü:</b> {conflict_note}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st_obj.markdown("### 📋 5 Rejimin Dinamik Eşik & Tetikleyici Karnesi")
    
    # Render 5 columns or tabs for the 5 regimes
    tabs = st_obj.tabs([
        "1. Enflasyon Şoku",
        "2. Likidite Şoku & Carry",
        "3. Reel Faiz Şoku",
        "4. Kredi Temerrüdü",
        "5. Likidite Rallisi (Risk-On)"
    ])
    
    det = eval_details
    
    # Tab 1
    with tabs[0]:
        st_obj.markdown("#### Rejim 1: Küresel Enflasyon & Stagflasyon Şoku (Tür: SHOCK)")
        r1 = det.get('r1', {})
        t1 = r1.get('t1', (0.0, 1.5, False))
        t2 = r1.get('t2', (0.0, -1.0, False))
        c1 = r1.get('c1', (0.0, 0.5, False))
        c2 = r1.get('c2', (0.0, 0.0, False))
        
        df_r1 = pd.DataFrame([
            {"Rol": "Tetikleyici (AND)", "Gösterge": "Petrol Şoku (WTI/Brent)", "Formül": "20 Günlük Getiri 52H Z-Skoru", "Güncel Z / Değer": f"{t1[0]:.2f}", "Eşik Şartı": "Z > 1.50", "Durum": "✅ TETİKLENDİ" if t1[2] else "❌ SAĞLANMADI"},
            {"Rol": "Tetikleyici (AND)", "Gösterge": "Navlun / Ticaret Çöküşü (BDI/BDRY)", "Formül": "52H Z-Skor Seviyesi", "Güncel Z / Değer": f"{t2[0]:.2f}", "Eşik Şartı": "Z < -1.00", "Durum": "✅ TETİKLENDİ" if t2[2] else "❌ SAĞLANMADI"},
            {"Rol": "Teyit (AND)", "Gösterge": "Kredi Stresi (FRED:HY OAS)", "Formül": "52H Z-Skor Seviyesi", "Güncel Z / Değer": f"{c1[0]:.2f}", "Eşik Şartı": "Z > 0.50", "Durum": "✅ TEYİT EDİLDİ" if c1[2] else "❌ TEYİT YOK"},
            {"Rol": "Teyit (AND)", "Gösterge": "Hisse/Tahvil Korelasyonu (SPX & UST10Y)", "Formül": "60 Günlük Kayan Korelasyon", "Güncel Z / Değer": f"{c2[0]:.2f}", "Eşik Şartı": "Korelasyon > 0.00", "Durum": "✅ TEYİT EDİLDİ" if c2[2] else "❌ TEYİT YOK"}
        ])
        st_obj.dataframe(df_r1, use_container_width=True)
        
    # Tab 2
    with tabs[1]:
        st_obj.markdown("#### Rejim 2: Sistemik Likidite Şoku & Carry Çöküşü (Tür: SHOCK)")
        r2 = det.get('r2', {})
        t1 = r2.get('t1', (0.0, 1.0, False))
        t2 = r2.get('t2', (0.0, -2.0, False))
        t3 = r2.get('t3', (0.0, 1.5, False))
        c1 = r2.get('c1', (0.0, -1.5, False))
        
        df_r2 = pd.DataFrame([
            {"Rol": "Tetikleyici (OR)", "Gösterge": "Geniş Dolar Gücü (DTWEXBGS)", "Formül": "5 Günlük Değişim 52H Z-Skoru", "Güncel Z / Değer": f"{t1[0]:.2f}", "Eşik Şartı": "Z > 1.00", "Durum": "✅ TETİKLENDİ" if t1[2] else "❌ SAĞLANMADI"},
            {"Rol": "Tetikleyici (OR)", "Gösterge": "JPY Carry Unwind (USD/JPY)", "Formül": "1 Günlük Değişim 52H Z-Skoru", "Güncel Z / Değer": f"{t2[0]:.2f}", "Eşik Şartı": "Z < -2.00", "Durum": "✅ TETİKLENDİ" if t2[2] else "❌ SAĞLANMADI"},
            {"Rol": "Tetikleyici (OR)", "Gösterge": "Volatilite Şoku (VIX)", "Formül": "52H Seviye Z-Skoru", "Güncel Z / Değer": f"{t3[0]:.2f}", "Eşik Şartı": "Z > 1.50", "Durum": "✅ TETİKLENDİ" if t3[2] else "❌ SAĞLANMADI"},
            {"Rol": "Teyit (AND)", "Gösterge": "Risk Varlığı Satışı (BTC + SPX)", "Formül": "5 Günlük Getiri 52H Z-Skoru", "Güncel Z / Değer": f"{c1[0]:.2f}", "Eşik Şartı": "Z < -1.50", "Durum": "✅ TEYİT EDİLDİ" if c1[2] else "❌ TEYİT YOK"}
        ])
        st_obj.dataframe(df_r2, use_container_width=True)
        
    # Tab 3
    with tabs[2]:
        st_obj.markdown("#### Rejim 3: Reel Faiz Şoku (Tür: SHOCK)")
        r3 = det.get('r3', {})
        t1 = r3.get('t1', (0.0, 1.5, False))
        t2 = r3.get('t2', (0.0, 0.5, False))
        t3 = r3.get('t3', (0.0, 0.35, False))
        st_r3 = r3.get('subtype', 'N/A')
        
        df_r3 = pd.DataFrame([
            {"Rol": "Ana Tetikleyici (AND)", "Gösterge": "Reel Faiz (FRED:DFII10 10Y TIPS)", "Formül": "1 Günlük Değişim 52H Z-Skoru", "Güncel Z / Değer": f"{t1[0]:.2f}", "Eşik Şartı": f"Z > {t1[1]:.2f}", "Durum": "✅ TETİKLENDİ" if t1[2] else "❌ SAĞLANMADI"},
            {"Rol": "Ayrıştırıcı (AND)", "Gösterge": "Breakeven Enflasyon (FRED:T10YIE)", "Formül": "52H Seviye Z-Skoru", "Güncel Z / Değer": f"{t2[0]:.2f}", "Eşik Şartı": f"Z < {t2[1]:.2f}", "Durum": "✅ SAĞLANDI" if t2[2] else "❌ SAĞLANMADI"},
            {"Rol": "Dolar Teyidi (AND)", "Gösterge": "Dolar Endeksi (DXY / DTWEX)", "Formül": "52H Seviye Z-Skoru", "Güncel Z / Değer": f"{t3[0]:.2f}", "Eşik Şartı": f"Z > {t3[1]:.2f}", "Durum": "✅ TEYİT EDİLDİ" if t3[2] else "❌ SAĞLANMADI"},
            {"Rol": "Eğri Alt-Tipi", "Gösterge": "Getiri Eğrisi (DGS2 & DGS10 Dinamiği)", "Formül": "ΔDGS2 vs ΔDGS10", "Güncel Z / Değer": st_r3, "Eşik Şartı": "Formül Kuralı", "Durum": "ℹ️ AKTİF TİP"}
        ])
        st_obj.dataframe(df_r3, use_container_width=True)
        
    # Tab 4
    with tabs[3]:
        st_obj.markdown("#### Rejim 4: Kredi Temerrüt Baskısı (Tür: SHOCK)")
        r4 = det.get('r4', {})
        t1 = r4.get('t1', (0.0, 2.0, False))
        t2 = r4.get('t2', (0.0, 0.0, False))
        c1 = r4.get('c1', (0.0, 1.0, False))
        
        df_r4 = pd.DataFrame([
            {"Rol": "Tetikleyici (AND)", "Gösterge": "Yüksek Getirili Spread (HY OAS)", "Formül": "52H Seviye Z-Skoru", "Güncel Z / Değer": f"{t1[0]:.2f}", "Eşik Şartı": "Z > 2.00", "Durum": "✅ TETİKLENDİ" if t1[2] else "❌ SAĞLANMADI"},
            {"Rol": "Trend Teyidi (AND)", "Gösterge": "HY OAS Genişleme Eğimi", "Formül": "10 Günlük Kayan Regresyon Eğimi", "Güncel Z / Değer": f"{t2[0]:.4f}", "Eşik Şartı": "Eğim > 0.00", "Durum": "✅ TETİKLENDİ" if t2[2] else "❌ SAĞLANMADI"},
            {"Rol": "Teyit (AND)", "Gösterge": "Yatırım Yapılabilir Spread (IG OAS)", "Formül": "52H Seviye Z-Skoru", "Güncel Z / Değer": f"{c1[0]:.2f}", "Eşik Şartı": "Z > 1.00", "Durum": "✅ TEYİT EDİLDİ" if c1[2] else "❌ TEYİT YOK"}
        ])
        st_obj.dataframe(df_r4, use_container_width=True)
        
    # Tab 5
    with tabs[4]:
        st_obj.markdown("#### Rejim 5: Küresel Likidite Rallisi (Risk-On) (Tür: RISK_ON)")
        r5 = det.get('r5', {})
        t1 = r5.get('t1', (0.0, -0.5, False))
        t2 = r5.get('t2', (0.0, (-1.0, 0.5), False))
        t3 = r5.get('t3', (50.0, 30.0, False))
        t4 = r5.get('t4', (0.0, 0.0, False))
        st_r5 = r5.get('subtype', 'N/A')
        
        df_r5 = pd.DataFrame([
            {"Rol": "Tetikleyici (AND)", "Gösterge": "Kredi Gücü (HY OAS)", "Formül": "52H Seviye Z-Skoru", "Güncel Z / Değer": f"{t1[0]:.2f}", "Eşik Şartı": "Z < -0.50", "Durum": "✅ TETİKLENDİ" if t1[2] else "❌ SAĞLANMADI"},
            {"Rol": "Tetikleyici (AND)", "Gösterge": "Dolar Rejimi (DTWEXBGS)", "Formül": "52H Seviye Z-Skoru", "Güncel Z / Değer": f"{t2[0]:.2f}", "Eşik Şartı": "-1.0 <= Z <= 0.5", "Durum": "✅ TETİKLENDİ" if t2[2] else "❌ SAĞLANMADI"},
            {"Rol": "Tetikleyici (AND)", "Gösterge": "Volatilite Sakinliği (VIX veya MOVE)", "Formül": "252 Günlük Yüzdelik (Percentile)", "Güncel Z / Değer": f"%{t3[0]:.1f}", "Eşik Şartı": "Yüzdelik < %30", "Durum": "✅ TETİKLENDİ" if t3[2] else "❌ SAĞLANMADI"},
            {"Rol": "Tetikleyici (AND)", "Gösterge": "Net Dolar Likiditesi (NDL)", "Formül": "52H Seviye Z-Skoru", "Güncel Z / Değer": f"{t4[0]:.2f}", "Eşik Şartı": "Z > 0.00", "Durum": "✅ TETİKLENDİ" if t4[2] else "❌ SAĞLANMADI"},
            {"Rol": "Alt-Tip (Post-Hoc)", "Gösterge": "Reflasyonist vs Goldilocks", "Formül": "DTWEX Z < -0.5 & Altın Fiyat İvmesi", "Güncel Z / Değer": st_r5, "Eşik Şartı": "Alt-Tip Kuralı", "Durum": "ℹ️ AKTİF TİP"}
        ])
        st_obj.dataframe(df_r5, use_container_width=True)
