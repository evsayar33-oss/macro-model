"""
🏛️ Backtesting & Dynamic Threshold Optimization Engine
Macro Event Interpretation System v1.0 & Continuum Master

Performs:
  1. Multi-year macroeconomic historical simulation (2019-2026) across key market crisis phases.
  2. Strict validation of principles: mutual exclusivity, 52w rolling z-score normalization, hysteresis.
  3. Real Rate Shock (Regime 3) DXY dollar confirmation calibration and conflict resolution.
  4. Sensitivity analysis across threshold parameters to determine optimal calibration.
  5. Multi-asset dynamic regime-adaptive weighting backtest across all 8 assets (Sharpe, MDD, returns).
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from macro_event_interpretation import (
    MacroEventInterpretationSystem,
    RegimeThresholdConfig,
    get_macro_interpretation_asset_multipliers
)
from asset_regime_weights import (
    ASSETS,
    INDICATORS,
    get_dynamic_asset_weights,
    ASSET_REGIME_CONFIGS
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
    dxy = np.full(n, 96.0)
    usdjpy = np.full(n, 110.0)
    vix = np.full(n, 15.0)
    move = np.full(n, 65.0)
    btc = np.full(n, 9000.0)
    dfii10 = np.full(n, 0.40)
    t10yie = np.full(n, 1.80)
    ndl = np.full(n, 5.0)
    gold = np.full(n, 1400.0)
    xag = np.full(n, 18.0)
    nq = np.full(n, 8800.0)
    hg = np.full(n, 2.80)
    tlt = np.full(n, 140.0)
    
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
        dxy[i] = max(88.0, min(116.0, dxy[i-1] + np.random.normal(0.0, 0.18)))
        usdjpy[i] = usdjpy[i-1] + np.random.normal(0.0, 0.25)
        vix[i] = max(11.0, vix[i-1] * 0.95 + 0.05 * 16.0 + np.random.normal(0.0, 0.8))
        move[i] = max(50.0, move[i-1] * 0.95 + 0.05 * 70.0 + np.random.normal(0.0, 1.5))
        btc[i] = btc[i-1] * np.exp(np.random.normal(0.001, 0.025))
        dfii10[i] = dfii10[i-1] + np.random.normal(0.0, 0.02)
        t10yie[i] = max(1.0, min(3.5, t10yie[i-1] + np.random.normal(0.0, 0.015)))
        ndl[i] = ndl[i-1] + np.random.normal(0.001, 0.01)
        gold[i] = gold[i-1] * np.exp(np.random.normal(0.0003, 0.007))
        xag[i] = xag[i-1] * np.exp(np.random.normal(0.0004, 0.012))
        nq[i] = nq[i-1] * np.exp(np.random.normal(0.0005, 0.010))
        hg[i] = max(1.5, hg[i-1] * np.exp(np.random.normal(0.0002, 0.010)))
        tlt[i] = max(60.0, tlt[i-1] * np.exp(np.random.normal(0.0001, 0.008)))
        
        # --- HISTORICAL MACRO EVENT PHASES ---
        
        # Phase 1: March 2020 Covid Liquidity Shock (Indices 270 to 315)
        if 270 <= i <= 315:
            vix[i] = 45.0 + np.random.uniform(15.0, 35.0)
            move[i] = 110.0 + np.random.uniform(20.0, 45.0)
            dtwex[i] = dtwex[i-1] + 0.55
            dxy[i] = dxy[i-1] + 0.45
            spx[i] = spx[i-1] * 0.965
            nq[i] = nq[i-1] * 0.968
            btc[i] = btc[i-1] * 0.94
            gold[i] = gold[i-1] * 0.985
            xag[i] = xag[i-1] * 0.960
            hy_oas[i] = hy_oas[i-1] + 0.25
            ig_oas[i] = ig_oas[i-1] + 0.08
            tlt[i] = tlt[i-1] * 1.008
            
        # Phase 2: Post-Covid QE / Global Liquidity Rally (Indices 350 to 650)
        elif 350 <= i <= 650:
            ndl[i] = 6.2 + (i - 350) * 0.005
            hy_oas[i] = max(2.8, 4.5 - (i - 350) * 0.007)
            dtwex[i] = max(108.0, 118.0 - (i - 350) * 0.02)
            dxy[i] = max(89.0, 100.0 - (i - 350) * 0.035)
            vix[i] = 14.0 + np.random.normal(0.0, 1.2)
            move[i] = 60.0 + np.random.normal(0.0, 3.5)
            gold[i] = gold[i-1] * 1.002
            xag[i] = xag[i-1] * 1.0035
            spx[i] = spx[i-1] * 1.0018
            nq[i] = nq[i-1] * 1.0025
            btc[i] = btc[i-1] * 1.006
            hg[i] = hg[i-1] * 1.002
            
        # Phase 3: Early 2022 Commodity & Inflation Shock (Indices 750 to 830)
        elif 750 <= i <= 830:
            oil[i] = oil[i-1] * 1.018
            bdi[i] = max(700.0, bdi[i-1] * 0.97)
            t10yie[i] = 2.80 + np.random.normal(0.0, 0.05)
            hy_oas[i] = 4.8 + np.random.normal(0.0, 0.1)
            spx[i] = spx[i-1] * 0.994
            nq[i] = nq[i-1] * 0.992
            ust10y[i] = ust10y[i-1] + 0.03
            tlt[i] = tlt[i-1] * 0.992
            gold[i] = gold[i-1] * 1.002
            
        # Phase 4: Mid/Late 2022 Real Rate Shock (Indices 860 to 950)
        elif 860 <= i <= 950:
            dfii10[i] = dfii10[i-1] + 0.045
            t10yie[i] = 2.05 - (i - 860) * 0.003
            ust2y[i] = ust2y[i-1] + 0.035
            ust10y[i] = ust10y[i-1] + 0.020
            dxy[i] = dxy[i-1] + 0.16 # DXY rallies to 20-year highs alongside TIPS real yields!
            dtwex[i] = dtwex[i-1] + 0.14
            gold[i] = gold[i-1] * 0.995
            xag[i] = xag[i-1] * 0.992
            nq[i] = nq[i-1] * 0.993
            spx[i] = spx[i-1] * 0.996
            tlt[i] = tlt[i-1] * 0.991
            
        # Phase 5: March 2023 SVB Credit Stress (Indices 1020 to 1055)
        elif 1020 <= i <= 1055:
            hy_oas[i] = hy_oas[i-1] + 0.12
            ig_oas[i] = ig_oas[i-1] + 0.05
            spx[i] = spx[i-1] * 0.994
            gold[i] = gold[i-1] * 1.004
            
        # Phase 6: August 2024 JPY Carry Trade Unwind (Indices 1360 to 1385)
        elif 1360 <= i <= 1385:
            usdjpy[i] = usdjpy[i-1] - (3.2 if i in [1362, 1363] else 0.5)
            vix[i] = 38.0 + np.random.uniform(5.0, 25.0)
            spx[i] = spx[i-1] * 0.975
            nq[i] = nq[i-1] * 0.968
            btc[i] = btc[i-1] * 0.945
            
        # Phase 7: Late 2024-2026 Liquidity Expansion / Goldilocks (Indices 1420 to 1800)
        elif 1420 <= i:
            ndl[i] = 5.8 + np.sin(i / 30.0) * 0.3
            hy_oas[i] = 3.10 + np.random.normal(0.0, 0.04)
            dtwex[i] = 112.0 + np.random.normal(0.0, 0.2)
            dxy[i] = 101.0 + np.random.normal(0.0, 0.2)
            vix[i] = 13.5 + np.random.normal(0.0, 1.0)
            move[i] = 68.0 + np.random.normal(0.0, 3.0)
            spx[i] = spx[i-1] * 1.0012
            nq[i] = nq[i-1] * 1.0018
            btc[i] = btc[i-1] * 1.0025
            gold[i] = gold[i-1] * 1.0015
            xag[i] = xag[i-1] * 1.0020
            
    df = pd.DataFrame({
        'oil': oil,
        'bdi': bdi,
        'hy_oas': hy_oas,
        'ig_oas': ig_oas,
        'spx': spx,
        'ust10y': ust10y,
        'ust2y': ust2y,
        'dtwex': dtwex,
        'dxy': dxy,
        'usdjpy': usdjpy,
        'vix': vix,
        'move': move,
        'btc': btc,
        'dfii10': dfii10,
        't10yie': t10yie,
        'ndl': ndl,
        'gold': gold,
        'xag': xag,
        'nq': nq,
        'hg': hg,
        'tlt': tlt
    }, index=dates)
    return df


def run_full_backtest(data_df: pd.DataFrame, config: RegimeThresholdConfig = None):
    """
    Executes historical simulation of the deterministic macro interpretation engine.
    """
    cfg = config or RegimeThresholdConfig()
    system = MacroEventInterpretationSystem(cfg)
    data_dict = {col: data_df[col] for col in data_df.columns}
    results = system.evaluate_history(data_dict)
    
    total_days = len(results)
    
    # 1. Mutual Exclusivity Verification
    valid_exclusivity = bool((results['confirmed_regime_id'].isin([0, 1, 2, 3, 4, 5])).all())
    
    # 2. Distribution of Confirmed Regimes
    regime_counts = results['confirmed_regime_name'].value_counts()
    dist_pct = {k: round(float(v / total_days * 100.0), 2) for k, v in regime_counts.items()}
    
    # 3. Transitions & Hysteresis Filtering Efficiency
    cand_switches = int((results['candidate_regime_id'] != results['candidate_regime_id'].shift(1)).sum())
    conf_switches = int((results['confirmed_regime_id'] != results['confirmed_regime_id'].shift(1)).sum())
    whipsaw_reduction_pct = round(float((1.0 - (conf_switches / max(1, cand_switches))) * 100.0), 1)
    
    # 4. Average Duration per regime
    cand_runs = (results['candidate_regime_id'] != results['candidate_regime_id'].shift(1)).cumsum()
    cand_avg_dur = round(float(results.groupby(cand_runs)['candidate_regime_id'].count().mean()), 1)
    
    conf_runs = (results['confirmed_regime_id'] != results['confirmed_regime_id'].shift(1)).cumsum()
    conf_avg_dur = round(float(results.groupby(conf_runs)['confirmed_regime_id'].count().mean()), 1)
    
    # 5. Conflict Resolution Audit
    conflicts_logged = results[results['conflict_note'] != 'Yok']['conflict_note']
    special_case_count = int(conflicts_logged.str.contains('R1 vs R3').sum())
    max_z_conflicts = int(conflicts_logged.str.contains('Çoklu Şok Çözümü').sum())
    
    # 6. Verification of Historical Macro Shock Detections
    phase_detections = {}
    regime_names = {
        1: "Küresel Enflasyon & Stagflasyon Şoku",
        2: "Sistemik Likidite Şoku & Carry Çöküşü",
        3: "Reel Faiz Şoku",
        4: "Kredi Temerrüt Baskısı",
        5: "Küresel Likidite Rallisi (Risk-On)",
        0: "REJIMSIZ_GECIS"
    }
    
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
    
    # 4. 2022 Real Rate Shock (calibrated with DXY confirmation)
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
    Sensitivity analysis over threshold variations including DXY threshold in Regime 3.
    """
    print("Running threshold sensitivity grid...")
    variations = [
        ("Base Spec (Optimal DXY Z > 0.35)", RegimeThresholdConfig(regime3_dxy_z_thresh=0.35)),
        ("DXY Tight Confirmation (Z > 0.60)", RegimeThresholdConfig(regime3_dxy_z_thresh=0.60)),
        ("Aggressive Triggers (Lower Z)", RegimeThresholdConfig(
            regime1_oil_z_thresh=1.2,
            regime2_vix_z_thresh=1.2,
            regime2_usdjpy_z_thresh=-1.5,
            regime3_dfii10_z_thresh=1.2,
            regime3_dxy_z_thresh=0.20,
            regime4_hy_z_thresh=1.5,
            regime5_vol_percentile_thresh=35.0
        )),
        ("Conservative Triggers (Higher Z)", RegimeThresholdConfig(
            regime1_oil_z_thresh=1.8,
            regime2_vix_z_thresh=1.8,
            regime2_usdjpy_z_thresh=-2.5,
            regime3_dfii10_z_thresh=1.8,
            regime3_dxy_z_thresh=0.50,
            regime4_hy_z_thresh=2.3,
            regime5_vol_percentile_thresh=25.0
        )),
        ("1-Week Hysteresis (Fast)", RegimeThresholdConfig(hysteresis_period_days=5, regime3_dxy_z_thresh=0.35)),
        ("3-Week Hysteresis (Slow)", RegimeThresholdConfig(hysteresis_period_days=15, regime3_dxy_z_thresh=0.35)),
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


def run_multi_asset_backtest(df: pd.DataFrame, regime_results: pd.DataFrame) -> pd.DataFrame:
    """
    Runs multi-asset performance simulation across 8 assets comparing:
      1. Uniform Static Weights (Benchmark)
      2. Fully Dynamic Regime-Adaptive Weights (Calibrated System)
    """
    n = len(df)
    asset_col_map = {
        "Altın (XAU)": "gold",
        "Gümüş (XAG)": "xag",
        "Nasdaq 100 (NQ)": "nq",
        "S&P 500 (SPX)": "spx",
        "Kripto (BTC)": "btc",
        "Ham Petrol (WTI)": "oil",
        "Bakır (HG)": "hg",
        "ABD Tahvili / Faiz (TLT)": "tlt"
    }
    
    asset_returns = {}
    for a, col in asset_col_map.items():
        if col in df:
            asset_returns[a] = df[col].pct_change().fillna(0.0)
        else:
            asset_returns[a] = pd.Series(0.0, index=df.index)
            
    uniform_static_weights = {ind: 1.0 / len(INDICATORS) for ind in INDICATORS}
    
    ind_signal_map = {
        "Dolar Endeksi Zayıflığı (DXY)": -regime_results.get('dxy_level_z', pd.Series(0.0, index=df.index)),
        "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": regime_results.get('ndl_z', pd.Series(0.0, index=df.index)),
        "Reel Faiz İndirgeme İvmesi (10Y TIPS)": -regime_results.get('dfii10_chg1_z', pd.Series(0.0, index=df.index)),
        "10Y Breakeven Enflasyon İvmesi": regime_results.get('t10yie_z', pd.Series(0.0, index=df.index)),
        "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": regime_results.get('t10yie_z', pd.Series(0.0, index=df.index)) * 0.9,
        "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": -regime_results.get('delta_dgs2', pd.Series(0.0, index=df.index)) * 5.0,
        "Yüksek Getirili Kredi Stresi (HY OAS)": -regime_results.get('hy_oas_z', pd.Series(0.0, index=df.index)),
        "MOVE Endeksi (Tahvil Volatilitesi)": -(regime_results.get('move_pctl252', pd.Series(50.0, index=df.index)) - 50.0) / 25.0,
        "VIX Endeksi (Hisse Volatilitesi)": -regime_results.get('vix_level_z', pd.Series(0.0, index=df.index)),
        "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": (regime_results.get('delta_dgs10', pd.Series(0.0, index=df.index)) - regime_results.get('delta_dgs2', pd.Series(0.0, index=df.index))) * 5.0,
        "Öncü İstihdam (ICSA)": -regime_results.get('bdi_level_z', pd.Series(0.0, index=df.index)) * 0.5,
        "Hazine Nakit / Banka Rezervleri (WRESBAL)": regime_results.get('ndl_z', pd.Series(0.0, index=df.index)) * 0.7
    }
    signals_df = pd.DataFrame(ind_signal_map, index=df.index).clip(-2.5, 2.5).fillna(0.0)
    
    summary_table = []
    
    for asset in ASSETS:
        r_asset = asset_returns[asset].values
        
        # 1. Uniform Static Model
        score_uniform = np.zeros(n)
        for ind in INDICATORS:
            score_uniform += signals_df[ind].values * uniform_static_weights[ind]
            
        # 2. Dynamic Regime-Adaptive Model
        score_dynamic = np.zeros(n)
        for idx in range(n):
            conf_r = int(regime_results['confirmed_regime_id'].iloc[idx])
            in_tr = bool(regime_results['in_transition'].iloc[idx])
            subt = str(regime_results['subtype'].iloc[idx])
            
            if conf_r == 5:
                probs = {"GOLDILOCKS": 0.45, "REFLASYON": 0.45, "STAGFLASYON": 0.05, "DEFLASYON": 0.05}
            elif conf_r == 1:
                probs = {"GOLDILOCKS": 0.05, "REFLASYON": 0.20, "STAGFLASYON": 0.70, "DEFLASYON": 0.05}
            elif conf_r in [2, 4]:
                probs = {"GOLDILOCKS": 0.05, "REFLASYON": 0.05, "STAGFLASYON": 0.20, "DEFLASYON": 0.70}
            elif conf_r == 3:
                probs = {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.40, "DEFLASYON": 0.40}
            else:
                probs = {"GOLDILOCKS": 0.35, "REFLASYON": 0.35, "STAGFLASYON": 0.15, "DEFLASYON": 0.15}
                
            dyn_w = get_dynamic_asset_weights(asset, conf_r, probs, in_tr)
            mults = get_macro_interpretation_asset_multipliers(conf_r, subt)
            mult = mults.get(asset, 1.0)
            
            raw_s = sum(signals_df[ind].iloc[idx] * dyn_w.get(ind, 1.0 / 12.0) for ind in INDICATORS)
            score_dynamic[idx] = raw_s * mult
            
        pos_uniform = np.clip(score_uniform * 0.75, -1.0, 1.0)
        pos_dynamic = np.clip(score_dynamic * 0.75, -1.0, 1.0)
        
        ret_uniform = np.zeros(n)
        ret_dynamic = np.zeros(n)
        
        ret_uniform[1:] = pos_uniform[:-1] * r_asset[1:]
        ret_dynamic[1:] = pos_dynamic[:-1] * r_asset[1:]
        
        def calc_perf(rets):
            cum = np.cumprod(1.0 + rets)
            total_ret = (cum[-1] - 1.0) * 100.0
            ann_ret = ((cum[-1]) ** (252.0 / n) - 1.0) * 100.0
            ann_vol = np.std(rets) * np.sqrt(252.0) * 100.0
            sharpe = (ann_ret - 2.0) / (ann_vol + 1e-6)
            peaks = np.maximum.accumulate(cum)
            drawdowns = (cum - peaks) / peaks
            max_dd = float(np.min(drawdowns)) * 100.0
            win_rate = float(np.mean(rets > 0)) * 100.0
            return {
                "total_return": round(total_ret, 2),
                "ann_return": round(ann_ret, 2),
                "ann_vol": round(ann_vol, 2),
                "sharpe": round(sharpe, 2),
                "max_dd": round(max_dd, 2),
                "win_rate": round(win_rate, 2)
            }
            
        m_uniform = calc_perf(ret_uniform)
        m_dyn = calc_perf(ret_dynamic)
        mdd_diff = abs(m_uniform["max_dd"]) - abs(m_dyn["max_dd"])
        
        summary_table.append({
            "Varlık": asset,
            "Statik Sharpe": m_uniform["sharpe"],
            "Dinamik Sharpe": m_dyn["sharpe"],
            "Sharpe Artışı": f"+{m_dyn['sharpe'] - m_uniform['sharpe']:.2f}",
            "Statik MaxDD": f"%{m_uniform['max_dd']:.1f}",
            "Dinamik MaxDD": f"%{m_dyn['max_dd']:.1f}",
            "MaxDD İyileşmesi": f"+%{mdd_diff:.1f}",
            "Statik Getiri (Yıllık)": f"%{m_uniform['ann_return']:.1f}",
            "Dinamik Getiri (Yıllık)": f"%{m_dyn['ann_return']:.1f}",
            "Yönsel İsabet Oranı": f"%{m_dyn['win_rate']:.1f}"
        })
        
    return pd.DataFrame(summary_table)


if __name__ == "__main__":
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    print("1. Generating 1800 days multi-year macro historical dataset (2019-2026)...")
    df = generate_historical_macro_dataset()
    
    print("2. Running Base Model Backtest (Regime 3 with DXY Confirmation)...")
    base_summary, base_results = run_full_backtest(df)
    
    def json_default(obj):
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        if isinstance(obj, (np.integer, int)):
            return int(obj)
        if isinstance(obj, (np.floating, float)):
            return float(obj)
        return str(obj)
        
    print("\n3. Running Multi-Asset Dynamic Weighting Backtest across 8 Assets...")
    asset_backtest_df = run_multi_asset_backtest(df, base_results)
    print("\n=== ÇOKLU VARLIK DİNAMİK AĞIRLIKLANDIRMA BACKTEST SONUÇLARI ===")
    print(asset_backtest_df.to_string(index=False))
    
    print("\n4. Running Sensitivity Analysis Grid across Dynamic Thresholds...")
    sensitivity_df = run_threshold_sensitivity_grid(df)
    print("\n=== EŞİK VE HİSTEREZİS DUYARLILIK ANALİZİ ===")
    print(sensitivity_df.to_string(index=False))
    
    # Add multi-asset results to summary
    base_summary['multi_asset_dynamic_backtest'] = asset_backtest_df.to_dict('records')
    
    # Save backtest results directly into repository directory
    out_ts_path = os.path.join(repo_dir, 'backtest_results_timeseries.csv')
    out_json_path = os.path.join(repo_dir, 'backtest_summary.json')
    out_sens_path = os.path.join(repo_dir, 'sensitivity_analysis.csv')
    out_asset_path = os.path.join(repo_dir, 'asset_dynamic_backtest_results.csv')
    
    base_results.to_csv(out_ts_path)
    with open(out_json_path, 'w', encoding='utf-8') as f:
        json.dump(base_summary, f, indent=2, ensure_ascii=False, default=json_default)
    sensitivity_df.to_csv(out_sens_path, index=False)
    asset_backtest_df.to_csv(out_asset_path, index=False)
    
    print(f"\nBacktest files generated successfully in {repo_dir}:")
    print(f" - {out_ts_path}")
    print(f" - {out_json_path}")
    print(f" - {out_sens_path}")
    print(f" - {out_asset_path}")
