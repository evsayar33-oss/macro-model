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
    shock_confirmation_days: int = 4     # Fast confirmation for sudden systemic shock triggers
    risk_on_confirmation_days: int = 7   # Confirmation for structural liquidity rally
    
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
        df = pd.DataFrame(data).ffill().bfill().dropna(how='all')
        features = pd.DataFrame(index=df.index)
        
        # 1. Regime 1 Indicators
        if 'oil' in df:
            ret_20d = df['oil'].pct_change(20)
            features['oil_ret20_z'] = calc_rolling_zscore(ret_20d, cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['oil_ret20_z'] = 0.0
            
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
            
        if 't10yie' in df:
            features['t10yie_z'] = calc_rolling_zscore(df['t10yie'], cfg.rolling_window_52w, cfg.min_periods_52w)
        else:
            features['t10yie_z'] = 0.0
            
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
            
        if 'gold' in df:
            features['gold_ret20'] = df['gold'].pct_change(20)
        else:
            features['gold_ret20'] = 0.0
            
        return features

    def evaluate_row(self, row: pd.Series) -> Dict[str, Any]:
        """
        Evaluates deterministic triggers, confirmations, conflict resolution, and sub-types.
        """
        cfg = self.config
        
        # --- REGIME 1 ---
        r1_t1 = row['oil_ret20_z'] > cfg.regime1_oil_z_thresh
        r1_t2 = row['bdi_level_z'] < cfg.regime1_bdi_z_thresh
        r1_triggers_met = r1_t1 and r1_t2
        
        r1_c1 = row['hy_oas_z'] > cfg.regime1_hy_z_thresh
        r1_c2 = row['spx_ust10_corr60'] > cfg.regime1_corr_thresh
        r1_confirms_met = r1_c1 and r1_c2
        
        r1_active = r1_triggers_met and r1_confirms_met
        r1_main_z = abs(row['oil_ret20_z'])
        
        # --- REGIME 2 ---
        r2_t1 = row['dtwex_chg5_z'] > cfg.regime2_dtwex_z_thresh
        r2_t2 = row['usdjpy_chg1_z'] < cfg.regime2_usdjpy_z_thresh
        r2_t3 = row['vix_level_z'] > cfg.regime2_vix_z_thresh
        r2_triggers_met = r2_t1 or r2_t2 or r2_t3
        
        r2_c1 = row['basket_ret5d_z'] < cfg.regime2_basket_z_thresh
        r2_confirms_met = r2_c1
        
        r2_active = r2_triggers_met and r2_confirms_met
        r2_main_z = max(
            abs(row['dtwex_chg5_z']) if r2_t1 else 0.0,
            abs(row['usdjpy_chg1_z']) if r2_t2 else 0.0,
            abs(row['vix_level_z']) if r2_t3 else 0.0,
        )
        
        # --- REGIME 3 ---
        r3_t1 = row['dfii10_chg1_z'] > cfg.regime3_dfii10_z_thresh
        r3_t2 = row['t10yie_z'] < cfg.regime3_t10yie_z_thresh
        r3_triggers_met = r3_t1 and r3_t2
        r3_active = r3_triggers_met
        r3_main_z = abs(row['dfii10_chg1_z'])
        
        # Sub-types for Regime 3
        d2 = row.get('delta_dgs2', 0.0)
        d10 = row.get('delta_dgs10', 0.0)
        if d2 < 0 and d10 > 0:
            r3_subtype = "Bear Steepener (Enflasyon/Term Premium)"
        elif d2 > 0 and d10 > 0 and d10 > d2:
            r3_subtype = "Bear Steepener (Fed Varyantı)"
        elif d2 > 0 and d10 > 0 and d2 > d10:
            r3_subtype = "Bear Flattener (Fed Sıkılaştırma Baskın)"
        elif d2 < 0 and d10 < 0:
            r3_subtype = "Bull Flattener/Steepener (Gevşeme - Tetiklemez)"
        else:
            r3_subtype = "Dengeli / Nötr Eğri"
            
        # --- REGIME 4 ---
        r4_t1 = row['hy_oas_z'] > cfg.regime4_hy_z_thresh
        r4_t2 = row['hy_oas_slope10'] > cfg.regime4_hy_slope_thresh
        r4_triggers_met = r4_t1 and r4_t2
        
        r4_c1 = row['ig_oas_z'] > cfg.regime4_ig_z_thresh
        r4_confirms_met = r4_c1
        
        r4_active = r4_triggers_met and r4_confirms_met
        r4_main_z = abs(row['hy_oas_z'])
        
        # --- REGIME 5 ---
        r5_t1 = row['hy_oas_z'] < cfg.regime5_hy_z_thresh
        r5_t2 = cfg.regime5_dtwex_z_min <= row['dtwex_level_z'] <= cfg.regime5_dtwex_z_max
        min_vol_pctl = min(row.get('vix_pctl252', 50.0), row.get('move_pctl252', 50.0))
        r5_t3 = min_vol_pctl < cfg.regime5_vol_percentile_thresh
        r5_t4 = row['ndl_z'] > cfg.regime5_ndl_z_thresh
        r5_triggers_met = r5_t1 and r5_t2 and r5_t3 and r5_t4
        r5_active = r5_triggers_met
        
        # Sub-types for Regime 5 (post-hoc)
        gold_ret = row.get('gold_ret20', 0.0)
        dtwex_z = row['dtwex_level_z']
        if dtwex_z < -0.5 and gold_ret > 0:
            r5_subtype = "Reflasyonist Risk-On"
        elif (-1.0 <= dtwex_z <= 0.5) and gold_ret <= 0:
            r5_subtype = "Klasik Goldilocks Risk-On"
        else:
            r5_subtype = "Dengeli Likidite Rallisi"
            
        # --- PRIORITY & CONFLICT RESOLUTION ---
        active_shocks = []
        if r1_active: active_shocks.append((1, r1_main_z))
        if r2_active: active_shocks.append((2, r2_main_z))
        if r3_active: active_shocks.append((3, r3_main_z))
        if r4_active: active_shocks.append((4, r4_main_z))
        
        candidate_regime_id: int = 0
        conflict_note: str = "Yok"
        active_subtype: str = "N/A"
        
        if active_shocks:
            if len(active_shocks) == 1:
                candidate_regime_id = active_shocks[0][0]
            else:
                shock_ids = [s[0] for s in active_shocks]
                # Special conflict case: Regime 1 vs Regime 3
                if set(shock_ids) == {1, 3}:
                    if row['t10yie_z'] > cfg.conflict_1_vs_3_t10yie_thresh:
                        candidate_regime_id = 1
                        conflict_note = f"Özel Çözüm: R1 vs R3 -> T10YIE_Z ({row['t10yie_z']:.2f}) > +0.5 => Rejim 1"
                    else:
                        candidate_regime_id = 3
                        conflict_note = f"Özel Çözüm: R1 vs R3 -> T10YIE_Z ({row['t10yie_z']:.2f}) <= +0.5 => Rejim 3"
                else:
                    best_shock = max(active_shocks, key=lambda x: x[1])
                    candidate_regime_id = best_shock[0]
                    conflict_note = f"Çoklu Şok Çözümü {shock_ids}: En yüksek |Z| ({best_shock[1]:.2f}) ile Rejim {candidate_regime_id}"
        elif r5_active:
            candidate_regime_id = 5
        else:
            candidate_regime_id = 0
            
        regime_names = {
            1: "Küresel Enflasyon & Stagflasyon Şoku",
            2: "Sistemik Likidite Şoku & Carry Çöküşü",
            3: "Reel Faiz Şoku",
            4: "Kredi Temerrüt Baskısı",
            5: "Küresel Likidite Rallisi (Risk-On)",
            0: "REJIMSIZ_GECIS"
        }
        candidate_regime_name = regime_names.get(candidate_regime_id, "REJIMSIZ_GECIS")
        
        if candidate_regime_id == 3:
            active_subtype = r3_subtype
        elif candidate_regime_id == 5:
            active_subtype = r5_subtype
            
        return {
            'candidate_id': candidate_regime_id,
            'candidate_name': candidate_regime_name,
            'subtype': active_subtype,
            'conflict_note': conflict_note,
            'r1_active': r1_active,
            'r2_active': r2_active,
            'r3_active': r3_active,
            'r4_active': r4_active,
            'r5_active': r5_active,
            'details': {
                'r1': {'t1': (float(row['oil_ret20_z']), cfg.regime1_oil_z_thresh, bool(r1_t1)),
                       't2': (float(row['bdi_level_z']), cfg.regime1_bdi_z_thresh, bool(r1_t2)),
                       'c1': (float(row['hy_oas_z']), cfg.regime1_hy_z_thresh, bool(r1_c1)),
                       'c2': (float(row['spx_ust10_corr60']), cfg.regime1_corr_thresh, bool(r1_c2))},
                'r2': {'t1': (float(row['dtwex_chg5_z']), cfg.regime2_dtwex_z_thresh, bool(r2_t1)),
                       't2': (float(row['usdjpy_chg1_z']), cfg.regime2_usdjpy_z_thresh, bool(r2_t2)),
                       't3': (float(row['vix_level_z']), cfg.regime2_vix_z_thresh, bool(r2_t3)),
                       'c1': (float(row['basket_ret5d_z']), cfg.regime2_basket_z_thresh, bool(r2_c1))},
                'r3': {'t1': (float(row['dfii10_chg1_z']), cfg.regime3_dfii10_z_thresh, bool(r3_t1)),
                       't2': (float(row['t10yie_z']), cfg.regime3_t10yie_z_thresh, bool(r3_t2)),
                       'subtype': r3_subtype},
                'r4': {'t1': (float(row['hy_oas_z']), cfg.regime4_hy_z_thresh, bool(r4_t1)),
                       't2': (float(row['hy_oas_slope10']), cfg.regime4_hy_slope_thresh, bool(r4_t2)),
                       'c1': (float(row['ig_oas_z']), cfg.regime4_ig_z_thresh, bool(r4_c1))},
                'r5': {'t1': (float(row['hy_oas_z']), cfg.regime5_hy_z_thresh, bool(r5_t1)),
                       't2': (float(row['dtwex_level_z']), (cfg.regime5_dtwex_z_min, cfg.regime5_dtwex_z_max), bool(r5_t2)),
                       't3': (float(min_vol_pctl), cfg.regime5_vol_percentile_thresh, bool(r5_t3)),
                       't4': (float(row['ndl_z']), cfg.regime5_ndl_z_thresh, bool(r5_t4)),
                       'subtype': r5_subtype}
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
        st_r3 = r3.get('subtype', 'N/A')
        
        df_r3 = pd.DataFrame([
            {"Rol": "Ana Tetikleyici (AND)", "Gösterge": "Reel Faiz (FRED:DFII10 10Y TIPS)", "Formül": "1 Günlük Değişim 52H Z-Skoru", "Güncel Z / Değer": f"{t1[0]:.2f}", "Eşik Şartı": "Z > 1.50", "Durum": "✅ TETİKLENDİ" if t1[2] else "❌ SAĞLANMADI"},
            {"Rol": "Ayrıştırıcı (AND)", "Gösterge": "Breakeven Enflasyon (FRED:T10YIE)", "Formül": "52H Seviye Z-Skoru", "Güncel Z / Değer": f"{t2[0]:.2f}", "Eşik Şartı": "Z < 0.50", "Durum": "✅ SAĞLANDI" if t2[2] else "❌ SAĞLANMADI"},
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
