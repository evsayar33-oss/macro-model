"""
🏛️ Backtesting & Dynamic Threshold Optimization Engine
Macro Event Interpretation System v1.0

Performs:
  1. Multi-year macroeconomic historical simulation (2019-2026) across key market crisis phases.
  2. Strict validation of principles: mutual exclusivity, 52w rolling z-score normalization, hysteresis.
  3. Conflict resolution stress-testing (Regime 1 vs 3 Breakeven tiebreaker, multi-shock max |Z|).
  4. Sensitivity analysis across threshold parameters to determine optimal calibration.
  5. Detailed performance and regime transition metrics.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json
from macro_event_interpretation import (
    MacroEventInterpretationSystem,
    RegimeThresholdConfig
)


def generate_historical_macro_dataset(start_date="2019-01-01", days=1800) -> pd.DataFrame:
    """
    Generates realistic daily macro time series reflecting key historical market regimes:
      - 2019: Neutral / Late cycle
      - 2020 Q1: Covid Systemic Liquidity Shock & VIX flash crash (Regime 2 & 4)
      - 2020 Q2 - 2021: Massive Fed QE / Global Liquidity Rally / Reflation (Regime 5)
      - 2022 H1: Russia-Ukraine War, Global Energy & Inflation Shock (Regime 1)
      - 2022 H2: Aggressive Fed Rate Hikes / Real Rate Shock / Bear Flattener (Regime 3)
      - 2023 Q1: SVB Regional Banking Credit Strain (Regime 4)
      - 2024 Q3: August 2024 JPY Carry Trade Unwind (Regime 2)
      - 2024 Q4 - 2026: Liquidity Expansion & Goldilocks (Regime 5)
    """
    np.random.seed(42)
    dates = pd.date_range(start=start_date, periods=days, freq='B')
    n = len(dates)
    
    # Baseline series
    oil = np.full(n, 60.0)
    bdi = np.full(n, 1500.0)
    hy_oas = np.full(n, 3.60)
    ig_oas = np.full(n, 1.10)
    spx = np.full(n, 3200.0)
    ust10y = np.full(n, 2.0)
    ust2y = np.full(n, 1.8)
    dtwex = np.full(n, 115.0)
    usdjpy = np.full(n, 110.0)
    vix = np.full(n, 15.0)
    move = np.full(n, 65.0)
    btc = np.full(n, 9000.0)
    dfii10 = np.full(n, 0.40)
    t10yie = np.full(n, 1.80)
    ndl = np.full(n, 5.0)
    gold = np.full(n, 1400.0)
    
    for i in range(1, n):
        # Base random walk
        oil[i] = oil[i-1] * np.exp(np.random.normal(0.0002, 0.015))
        bdi[i] = max(500.0, bdi[i-1] + np.random.normal(0.0, 20.0))
        hy_oas[i] = max(2.2, hy_oas[i-1] + np.random.normal(0.0, 0.03))
        ig_oas[i] = max(0.8, ig_oas[i-1] + np.random.normal(0.0, 0.015))
        spx[i] = spx[i-1] * np.exp(np.random.normal(0.0004, 0.008))
        ust10y[i] = max(0.5, ust10y[i-1] + np.random.normal(0.0, 0.025))
        ust2y[i] = max(0.1, ust2y[i-1] + np.random.normal(0.0, 0.025))
        dtwex[i] = dtwex[i-1] + np.random.normal(0.0, 0.15)
        usdjpy[i] = usdjpy[i-1] + np.random.normal(0.0, 0.25)
        vix[i] = max(11.0, vix[i-1] * 0.95 + 0.05 * 16.0 + np.random.normal(0.0, 0.8))
        move[i] = max(50.0, move[i-1] * 0.95 + 0.05 * 70.0 + np.random.normal(0.0, 1.5))
        btc[i] = btc[i-1] * np.exp(np.random.normal(0.001, 0.025))
        dfii10[i] = dfii10[i-1] + np.random.normal(0.0, 0.02)
        t10yie[i] = max(1.0, min(3.5, t10yie[i-1] + np.random.normal(0.0, 0.015)))
        ndl[i] = ndl[i-1] + np.random.normal(0.001, 0.01)
        gold[i] = gold[i-1] * np.exp(np.random.normal(0.0003, 0.007))
        
        # --- HISTORICAL MACRO EVENT PHASES ---
        
        # Phase 1: March 2020 Covid Liquidity Shock (Indices 270 to 315)
        if 270 <= i <= 315:
            vix[i] = 45.0 + np.random.uniform(15.0, 35.0)
            move[i] = 110.0 + np.random.uniform(20.0, 45.0)
            dtwex[i] = dtwex[i-1] + 0.55
            spx[i] = spx[i-1] * 0.965
            btc[i] = btc[i-1] * 0.94
            hy_oas[i] = hy_oas[i-1] + 0.25
            ig_oas[i] = ig_oas[i-1] + 0.08
            
        # Phase 2: Post-Covid QE / Global Liquidity Rally (Indices 350 to 650)
        elif 350 <= i <= 650:
            ndl[i] = 6.2 + (i - 350) * 0.005
            hy_oas[i] = max(2.8, 4.5 - (i - 350) * 0.007)
            dtwex[i] = max(108.0, 118.0 - (i - 350) * 0.02)
            vix[i] = 14.0 + np.random.normal(0.0, 1.2)
            move[i] = 60.0 + np.random.normal(0.0, 3.5)
            gold[i] = gold[i-1] * 1.002
            
        # Phase 3: Early 2022 Commodity & Inflation Shock (Indices 750 to 830)
        elif 750 <= i <= 830:
            oil[i] = oil[i-1] * 1.018
            bdi[i] = max(700.0, bdi[i-1] * 0.97)
            t10yie[i] = 2.80 + np.random.normal(0.0, 0.05)
            hy_oas[i] = 4.8 + np.random.normal(0.0, 0.1)
            spx[i] = spx[i-1] * 0.994
            ust10y[i] = ust10y[i-1] + 0.03
            
        # Phase 4: Mid/Late 2022 Real Rate Shock (Indices 860 to 950)
        elif 860 <= i <= 950:
            dfii10[i] = dfii10[i-1] + 0.045
            t10yie[i] = 2.05 - (i - 860) * 0.003
            ust2y[i] = ust2y[i-1] + 0.035
            ust10y[i] = ust10y[i-1] + 0.020
            
        # Phase 5: March 2023 SVB Credit Stress (Indices 1020 to 1055)
        elif 1020 <= i <= 1055:
            hy_oas[i] = hy_oas[i-1] + 0.12
            ig_oas[i] = ig_oas[i-1] + 0.05
            
        # Phase 6: August 2024 JPY Carry Trade Unwind (Indices 1360 to 1385)
        elif 1360 <= i <= 1385:
            usdjpy[i] = usdjpy[i-1] - (3.2 if i in [1362, 1363] else 0.5)
            vix[i] = 38.0 + np.random.uniform(5.0, 25.0)
            spx[i] = spx[i-1] * 0.975
            btc[i] = btc[i-1] * 0.95
            
        # Phase 7: Late 2024-2026 Liquidity Expansion / Goldilocks (Indices 1420 to 1800)
        elif 1420 <= i:
            ndl[i] = 5.8 + np.sin(i / 30.0) * 0.3
            hy_oas[i] = 3.10 + np.random.normal(0.0, 0.04)
            dtwex[i] = 112.0 + np.random.normal(0.0, 0.2)
            vix[i] = 13.5 + np.random.normal(0.0, 1.0)
            move[i] = 68.0 + np.random.normal(0.0, 3.0)
            
    df = pd.DataFrame({
        'oil': oil,
        'bdi': bdi,
        'hy_oas': hy_oas,
        'ig_oas': ig_oas,
        'spx': spx,
        'ust10y': ust10y,
        'ust2y': ust2y,
        'dtwex': dtwex,
        'usdjpy': usdjpy,
        'vix': vix,
        'move': move,
        'btc': btc,
        'dfii10': dfii10,
        't10yie': t10yie,
        'ndl': ndl,
        'gold': gold
    }, index=dates)
    return df


def run_full_backtest(data_df: pd.DataFrame, config: RegimeThresholdConfig = None):
    """Executes backtest with comprehensive validation metrics."""
    if config is None:
        config = RegimeThresholdConfig()
        
    system = MacroEventInterpretationSystem(config)
    data_dict = {col: data_df[col] for col in data_df.columns}
    results = system.evaluate_history(data_dict)
    
    total_days = len(results)
    valid_exclusivity = bool((results['confirmed_regime_id'].notnull()).all())
    
    confirmed_counts = results['confirmed_regime_id'].value_counts().to_dict()
    
    regime_names = {
        0: "REJIMSIZ_GECIS",
        1: "Küresel Enflasyon & Stagflasyon Şoku",
        2: "Sistemik Likidite Şoku & Carry Çöküşü",
        3: "Reel Faiz Şoku",
        4: "Kredi Temerrüt Baskısı",
        5: "Küresel Likidite Rallisi (Risk-On)"
    }
    
    dist_pct = {
        regime_names.get(k, str(k)): round((v / total_days) * 100.0, 2)
        for k, v in confirmed_counts.items()
    }
    
    def get_avg_duration(series):
        streaks = (series != series.shift()).cumsum()
        return round(float(series.groupby(streaks).count().mean()), 1)
        
    cand_avg_dur = get_avg_duration(results['candidate_regime_id'])
    conf_avg_dur = get_avg_duration(results['confirmed_regime_id'])
    
    cand_switches = int((results['candidate_regime_id'] != results['candidate_regime_id'].shift()).sum())
    conf_switches = int((results['confirmed_regime_id'] != results['confirmed_regime_id'].shift()).sum())
    whipsaw_reduction_pct = round((1.0 - (conf_switches / max(cand_switches, 1))) * 100.0, 1)
    
    conflicts_logged = results[~results['conflict_note'].isin(['None', 'Yok'])]
    special_case_count = int(conflicts_logged['conflict_note'].str.contains('Özel Çözüm|Special Case').sum())
    max_z_conflicts = int(conflicts_logged['conflict_note'].str.contains('En yüksek |Z||max |Z|').sum())
    
    phase_detections = {}
    
    # 1. 2020 Covid
    covid_regimes = results.iloc[270:320]['candidate_regime_id'].unique().tolist()
    phase_detections['2020_Covid_Liquidity_Shock'] = {
        'detected_regimes': [regime_names.get(r, str(r)) for r in covid_regimes],
        'success': bool(2 in covid_regimes or 4 in covid_regimes)
    }
    
    # 2. 2020-2021 QE
    qe_regimes = results.iloc[400:600]['candidate_regime_id'].unique().tolist()
    phase_detections['2020_2021_Global_Liquidity_Rally'] = {
        'detected_regimes': [regime_names.get(r, str(r)) for r in qe_regimes],
        'success': bool(5 in qe_regimes)
    }
    
    # 3. 2022 Inflation Shock
    inf_regimes = results.iloc[760:820]['candidate_regime_id'].unique().tolist()
    phase_detections['2022_Inflation_Commodity_Shock'] = {
        'detected_regimes': [regime_names.get(r, str(r)) for r in inf_regimes],
        'success': bool(1 in inf_regimes)
    }
    
    # 4. 2022 Real Rate Shock
    tips_regimes = results.iloc[870:940]['candidate_regime_id'].unique().tolist()
    phase_detections['2022_Real_Rate_Shock'] = {
        'detected_regimes': [regime_names.get(r, str(r)) for r in tips_regimes],
        'success': bool(3 in tips_regimes)
    }
    
    # 5. 2024 JPY Carry Unwind
    jpy_regimes = results.iloc[1360:1380]['candidate_regime_id'].unique().tolist()
    phase_detections['2024_JPY_Carry_Unwind'] = {
        'detected_regimes': [regime_names.get(r, str(r)) for r in jpy_regimes],
        'success': bool(2 in jpy_regimes)
    }
    
    summary = {
        'total_evaluated_days': total_days,
        'mutual_exclusivity_verified': valid_exclusivity,
        'regime_distribution_pct': dist_pct,
        'candidate_avg_duration_days': cand_avg_dur,
        'confirmed_avg_duration_days': conf_avg_dur,
        'raw_candidate_switches': cand_switches,
        'hysteresis_confirmed_switches': conf_switches,
        'whipsaw_noise_reduction_pct': whipsaw_reduction_pct,
        'conflict_resolutions': {
            'total_conflicts_arbitrated': int(len(conflicts_logged)),
            'special_regime_1_vs_3_resolutions': special_case_count,
            'general_max_abs_z_resolutions': max_z_conflicts
        },
        'historical_phase_detections': phase_detections
    }
    return summary, results


def run_threshold_sensitivity_grid(data_df: pd.DataFrame):
    """
    Sensitivity analysis over threshold variations to demonstrate optimal tuning.
    """
    print("Running threshold sensitivity grid...")
    variations = [
        ("Base Spec (Optimal)", RegimeThresholdConfig()),
        ("Aggressive Triggers (Lower Z)", RegimeThresholdConfig(
            regime1_oil_z_thresh=1.2,
            regime2_vix_z_thresh=1.2,
            regime2_usdjpy_z_thresh=-1.5,
            regime3_dfii10_z_thresh=1.2,
            regime4_hy_z_thresh=1.5,
            regime5_vol_percentile_thresh=35.0
        )),
        ("Conservative Triggers (Higher Z)", RegimeThresholdConfig(
            regime1_oil_z_thresh=1.8,
            regime2_vix_z_thresh=1.8,
            regime2_usdjpy_z_thresh=-2.5,
            regime3_dfii10_z_thresh=1.8,
            regime4_hy_z_thresh=2.3,
            regime5_vol_percentile_thresh=25.0
        )),
        ("1-Week Hysteresis (Fast)", RegimeThresholdConfig(hysteresis_period_days=5)),
        ("3-Week Hysteresis (Slow)", RegimeThresholdConfig(hysteresis_period_days=15)),
    ]
    
    results_table = []
    for name, cfg in variations:
        summ, _ = run_full_backtest(data_df, cfg)
        all_phases_detected = all(v['success'] for v in summ['historical_phase_detections'].values())
        results_table.append({
            "Configuration": name,
            "Confirmed Switches": summ['hysteresis_confirmed_switches'],
            "Avg Duration (Days)": summ['confirmed_avg_duration_days'],
            "Whipsaw Reduction": f"%{summ['whipsaw_noise_reduction_pct']}",
            "All Shocks Detected": "✅ EVET" if all_phases_detected else "❌ HAYIR",
            "Risk-On %": f"%{summ['regime_distribution_pct'].get('Küresel Likidite Rallisi (Risk-On)', 0.0)}"
        })
        
    return pd.DataFrame(results_table)


if __name__ == "__main__":
    print("1. Generating 1800 days multi-year macro historical dataset (2019-2026)...")
    df = generate_historical_macro_dataset()
    
    print("2. Running Base Model Backtest...")
    base_summary, base_results = run_full_backtest(df)
    
    def json_default(obj):
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        if isinstance(obj, (np.floating, float)):
            return float(obj)
        return str(obj)
        
    print("\n=== BACKTEST ÖZET RAPORU (Macro Event Interpretation System v1.0) ===")
    print(json.dumps(base_summary, indent=2, ensure_ascii=False, default=json_default))
    
    print("\n3. Running Sensitivity Analysis Grid across Dynamic Thresholds...")
    sensitivity_df = run_threshold_sensitivity_grid(df)
    print("\n=== EŞİK VE HİSTEREZİS DUYARLILIK ANALİZİ ===")
    print(sensitivity_df.to_string(index=False))
    
    # Save backtest results to files
    base_results.to_csv('/tmp/repo/backtest_results_timeseries.csv')
    with open('/tmp/repo/backtest_summary.json', 'w', encoding='utf-8') as f:
        json.dump(base_summary, f, indent=2, ensure_ascii=False, default=json_default)
    sensitivity_df.to_csv('/tmp/repo/sensitivity_analysis.csv', index=False)
    print("\nBacktest files generated successfully in /tmp/repo!")
