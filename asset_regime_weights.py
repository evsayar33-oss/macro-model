"""
🏛️ Asset-Specific Regime-Adaptive Dynamic Weighting Engine
Macro Event Interpretation System v1.0 & Continuum Master

Dynamically modulates the weights of 12 macro indicators for each asset based on:
  1. The analyzed asset's empirical structural sensitivities.
  2. The 5 Deterministic Macro Regimes (Shocks 1-4 & Risk-On 5).
  3. The 4 Continuum Fuzzy Regimes (Goldilocks, Reflation, Stagflation, Deflation).
  4. Hysteresis confirmation state (smooth transition blending).
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

INDICATORS = [
    "Dolar Endeksi Zayıflığı (DXY)",
    "G4 Küresel Süper Likidite (Fed+ECB+BoJ)",
    "Reel Faiz İndirgeme İvmesi (10Y TIPS)",
    "10Y Breakeven Enflasyon İvmesi",
    "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)",
    "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)",
    "Yüksek Getirili Kredi Stresi (HY OAS)",
    "MOVE Endeksi (Tahvil Volatilitesi)",
    "VIX Endeksi (Hisse Volatilitesi)",
    "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)",
    "Öncü İstihdam (ICSA)",
    "Hazine Nakit / Banka Rezervleri (WRESBAL)"
]

ASSETS = [
    "Altın (XAU)",
    "Gümüş (XAG)",
    "Nasdaq 100 (NQ)",
    "S&P 500 (SPX)",
    "Kripto (BTC)",
    "Ham Petrol (WTI)",
    "Bakır (HG)",
    "ABD Tahvili / Faiz (TLT)"
]

# -------------------------------------------------------------------------
# CALIBRATED ASSET WEIGHT SPECIFICATIONS (Empirically Optimized via Backtest)
# -------------------------------------------------------------------------
# Each asset defines:
#   'continuum': {indicator: {'GOLDILOCKS': w, 'REFLASYON': w, 'STAGFLASYON': w, 'DEFLASYON': w}}
#   'deterministic': {regime_id (0..5): {indicator: w}}
# -------------------------------------------------------------------------

ASSET_REGIME_CONFIGS: Dict[str, Dict[str, Any]] = {
    "Altın (XAU)": {
        "continuum": {
            "Dolar Endeksi Zayıflığı (DXY)": {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.16, "DEFLASYON": 0.12},
            "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": {"GOLDILOCKS": 0.16, "REFLASYON": 0.16, "STAGFLASYON": 0.10, "DEFLASYON": 0.10},
            "Reel Faiz İndirgeme İvmesi (10Y TIPS)": {"GOLDILOCKS": 0.18, "REFLASYON": 0.12, "STAGFLASYON": 0.16, "DEFLASYON": 0.22},
            "10Y Breakeven Enflasyon İvmesi": {"GOLDILOCKS": 0.10, "REFLASYON": 0.22, "STAGFLASYON": 0.20, "DEFLASYON": 0.06},
            "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": {"GOLDILOCKS": 0.08, "REFLASYON": 0.16, "STAGFLASYON": 0.16, "DEFLASYON": 0.04},
            "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": {"GOLDILOCKS": 0.08, "REFLASYON": 0.06, "STAGFLASYON": 0.06, "DEFLASYON": 0.14},
            "Yüksek Getirili Kredi Stresi (HY OAS)": {"GOLDILOCKS": 0.06, "REFLASYON": 0.04, "STAGFLASYON": 0.06, "DEFLASYON": 0.12},
            "MOVE Endeksi (Tahvil Volatilitesi)": {"GOLDILOCKS": 0.06, "REFLASYON": 0.03, "STAGFLASYON": 0.05, "DEFLASYON": 0.10},
            "VIX Endeksi (Hisse Volatilitesi)": {"GOLDILOCKS": 0.03, "REFLASYON": 0.02, "STAGFLASYON": 0.02, "DEFLASYON": 0.05},
            "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": {"GOLDILOCKS": 0.03, "REFLASYON": 0.01, "STAGFLASYON": 0.01, "DEFLASYON": 0.02},
            "Öncü İstihdam (ICSA)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.01, "STAGFLASYON": 0.01, "DEFLASYON": 0.02},
            "Hazine Nakit / Banka Rezervleri (WRESBAL)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.01, "STAGFLASYON": 0.01, "DEFLASYON": 0.01}
        },
        "deterministic": {
            1: { # Küresel Enflasyon & Stagflasyon Şoku
                "10Y Breakeven Enflasyon İvmesi": 0.22, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.18,
                "Dolar Endeksi Zayıflığı (DXY)": 0.16, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.14,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.12, "MOVE Endeksi (Tahvil Volatilitesi)": 0.06,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.04, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.04,
                "VIX Endeksi (Hisse Volatilitesi)": 0.02, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.01,
                "Öncü İstihdam (ICSA)": 0.005, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.005
            },
            2: { # Sistemik Likidite Şoku & Carry Çöküşü
                "Dolar Endeksi Zayıflığı (DXY)": 0.26, "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.20,
                "VIX Endeksi (Hisse Volatilitesi)": 0.14, "MOVE Endeksi (Tahvil Volatilitesi)": 0.14,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.10, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.08,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.04, "10Y Breakeven Enflasyon İvmesi": 0.02,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.01, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.005,
                "Öncü İstihdam (ICSA)": 0.002, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.003
            },
            3: { # Reel Faiz Şoku (Surging Real Yields & USD rally)
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.32, "Dolar Endeksi Zayıflığı (DXY)": 0.24,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.14, "10Y Breakeven Enflasyon İvmesi": 0.10,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.08, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.04,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.03, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.02,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.015, "VIX Endeksi (Hisse Volatilitesi)": 0.01,
                "Öncü İstihdam (ICSA)": 0.002, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.003
            },
            4: { # Kredi Temerrüt Baskısı
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.22, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.18,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.16, "Dolar Endeksi Zayıflığı (DXY)": 0.16,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.12, "VIX Endeksi (Hisse Volatilitesi)": 0.08,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.04, "10Y Breakeven Enflasyon İvmesi": 0.02,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.01, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.005,
                "Öncü İstihdam (ICSA)": 0.002, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.003
            },
            5: { # Küresel Likidite Rallisi (Risk-On)
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.24, "Dolar Endeksi Zayıflığı (DXY)": 0.20,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.16, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.14,
                "10Y Breakeven Enflasyon İvmesi": 0.12, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.06,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.04, "MOVE Endeksi (Tahvil Volatilitesi)": 0.02,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.01, "VIX Endeksi (Hisse Volatilitesi)": 0.005,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.003, "Öncü İstihdam (ICSA)": 0.002
            },
            0: { # Neutral Baseline
                "Dolar Endeksi Zayıflığı (DXY)": 0.18, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.18,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.16, "10Y Breakeven Enflasyon İvmesi": 0.14,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.10, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.08,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.06, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.05,
                "VIX Endeksi (Hisse Volatilitesi)": 0.02, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.015,
                "Öncü İstihdam (ICSA)": 0.01, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.005
            }
        }
    },

    "Gümüş (XAG)": {
        "continuum": {
            "Dolar Endeksi Zayıflığı (DXY)": {"GOLDILOCKS": 0.18, "REFLASYON": 0.18, "STAGFLASYON": 0.16, "DEFLASYON": 0.10},
            "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": {"GOLDILOCKS": 0.18, "REFLASYON": 0.18, "STAGFLASYON": 0.10, "DEFLASYON": 0.08},
            "Reel Faiz İndirgeme İvmesi (10Y TIPS)": {"GOLDILOCKS": 0.16, "REFLASYON": 0.10, "STAGFLASYON": 0.14, "DEFLASYON": 0.20},
            "10Y Breakeven Enflasyon İvmesi": {"GOLDILOCKS": 0.12, "REFLASYON": 0.24, "STAGFLASYON": 0.22, "DEFLASYON": 0.06},
            "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": {"GOLDILOCKS": 0.08, "REFLASYON": 0.14, "STAGFLASYON": 0.16, "DEFLASYON": 0.04},
            "Öncü İstihdam (ICSA)": {"GOLDILOCKS": 0.06, "REFLASYON": 0.04, "STAGFLASYON": 0.04, "DEFLASYON": 0.08},
            "Yüksek Getirili Kredi Stresi (HY OAS)": {"GOLDILOCKS": 0.06, "REFLASYON": 0.04, "STAGFLASYON": 0.06, "DEFLASYON": 0.14},
            "MOVE Endeksi (Tahvil Volatilitesi)": {"GOLDILOCKS": 0.06, "REFLASYON": 0.02, "STAGFLASYON": 0.04, "DEFLASYON": 0.10},
            "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": {"GOLDILOCKS": 0.04, "REFLASYON": 0.03, "STAGFLASYON": 0.04, "DEFLASYON": 0.12},
            "VIX Endeksi (Hisse Volatilitesi)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.01, "STAGFLASYON": 0.02, "DEFLASYON": 0.04},
            "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.01, "STAGFLASYON": 0.01, "DEFLASYON": 0.02},
            "Hazine Nakit / Banka Rezervleri (WRESBAL)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.01, "STAGFLASYON": 0.01, "DEFLASYON": 0.02}
        },
        "deterministic": {
            1: {
                "10Y Breakeven Enflasyon İvmesi": 0.24, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.18,
                "Dolar Endeksi Zayıflığı (DXY)": 0.16, "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.14,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.12, "Öncü İstihdam (ICSA)": 0.08,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.04, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.02,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.01, "VIX Endeksi (Hisse Volatilitesi)": 0.005,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.003, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.002
            },
            2: {
                "Dolar Endeksi Zayıflığı (DXY)": 0.26, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.18,
                "VIX Endeksi (Hisse Volatilitesi)": 0.16, "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.16,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.12, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.06,
                "Öncü İstihdam (ICSA)": 0.03, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.015,
                "10Y Breakeven Enflasyon İvmesi": 0.01, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.003,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            3: {
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.30, "Dolar Endeksi Zayıflığı (DXY)": 0.24,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.14, "MOVE Endeksi (Tahvil Volatilitesi)": 0.12,
                "10Y Breakeven Enflasyon İvmesi": 0.08, "Öncü İstihdam (ICSA)": 0.05,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.04, "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.02,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.005, "VIX Endeksi (Hisse Volatilitesi)": 0.002,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.002, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            4: {
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.26, "VIX Endeksi (Hisse Volatilitesi)": 0.18,
                "Dolar Endeksi Zayıflığı (DXY)": 0.16, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.14,
                "Öncü İstihdam (ICSA)": 0.12, "MOVE Endeksi (Tahvil Volatilitesi)": 0.08,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.04, "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.01,
                "10Y Breakeven Enflasyon İvmesi": 0.005, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.002,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.002, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            5: {
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.26, "Dolar Endeksi Zayıflığı (DXY)": 0.20,
                "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.14, "10Y Breakeven Enflasyon İvmesi": 0.14,
                "Öncü İstihdam (ICSA)": 0.12, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.08,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.04, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.01,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.005, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.002,
                "VIX Endeksi (Hisse Volatilitesi)": 0.002, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001
            },
            0: {
                "Dolar Endeksi Zayıflığı (DXY)": 0.18, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.16,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.16, "10Y Breakeven Enflasyon İvmesi": 0.14,
                "Öncü İstihdam (ICSA)": 0.10, "HY OAS": 0.08, "MOVE": 0.06,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.05, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.03,
                "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.02, "VIX Endeksi (Hisse Volatilitesi)": 0.01,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.01
            }
        }
    },

    "Nasdaq 100 (NQ)": {
        "continuum": {
            "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": {"GOLDILOCKS": 0.20, "REFLASYON": 0.16, "STAGFLASYON": 0.08, "DEFLASYON": 0.10},
            "Reel Faiz İndirgeme İvmesi (10Y TIPS)": {"GOLDILOCKS": 0.20, "REFLASYON": 0.14, "STAGFLASYON": 0.18, "DEFLASYON": 0.18},
            "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": {"GOLDILOCKS": 0.14, "REFLASYON": 0.10, "STAGFLASYON": 0.12, "DEFLASYON": 0.16},
            "MOVE Endeksi (Tahvil Volatilitesi)": {"GOLDILOCKS": 0.10, "REFLASYON": 0.08, "STAGFLASYON": 0.12, "DEFLASYON": 0.12},
            "VIX Endeksi (Hisse Volatilitesi)": {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.12, "DEFLASYON": 0.14},
            "Yüksek Getirili Kredi Stresi (HY OAS)": {"GOLDILOCKS": 0.08, "REFLASYON": 0.06, "STAGFLASYON": 0.10, "DEFLASYON": 0.14},
            "Dolar Endeksi Zayıflığı (DXY)": {"GOLDILOCKS": 0.08, "REFLASYON": 0.12, "STAGFLASYON": 0.08, "DEFLASYON": 0.04},
            "Hazine Nakit / Banka Rezervleri (WRESBAL)": {"GOLDILOCKS": 0.04, "REFLASYON": 0.08, "STAGFLASYON": 0.04, "DEFLASYON": 0.02},
            "10Y Breakeven Enflasyon İvmesi": {"GOLDILOCKS": 0.02, "REFLASYON": 0.08, "STAGFLASYON": 0.06, "DEFLASYON": 0.02},
            "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.04, "STAGFLASYON": 0.04, "DEFLASYON": 0.04},
            "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.04, "STAGFLASYON": 0.04, "DEFLASYON": 0.02},
            "Öncü İstihdam (ICSA)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.02, "STAGFLASYON": 0.02, "DEFLASYON": 0.02}
        },
        "deterministic": {
            1: {
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.26, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.18,
                "10Y Breakeven Enflasyon İvmesi": 0.16, "MOVE Endeksi (Tahvil Volatilitesi)": 0.14,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.12, "Dolar Endeksi Zayıflığı (DXY)": 0.06,
                "VIX Endeksi (Hisse Volatilitesi)": 0.04, "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.02,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.01, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.005,
                "Öncü İstihdam (ICSA)": 0.003, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.002
            },
            2: {
                "VIX Endeksi (Hisse Volatilitesi)": 0.26, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.20,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.18, "MOVE Endeksi (Tahvil Volatilitesi)": 0.16,
                "Dolar Endeksi Zayıflığı (DXY)": 0.10, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.06,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.02, "10Y Breakeven Enflasyon İvmesi": 0.01,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.005, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.002,
                "Öncü İstihdam (ICSA)": 0.002, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.001
            },
            3: {
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.34, "MOVE Endeksi (Tahvil Volatilitesi)": 0.20,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.16, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.12,
                "Dolar Endeksi Zayıflığı (DXY)": 0.10, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.04,
                "VIX Endeksi (Hisse Volatilitesi)": 0.02, "10Y Breakeven Enflasyon İvmesi": 0.01,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.005, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.002,
                "Öncü İstihdam (ICSA)": 0.002, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            4: {
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.28, "VIX Endeksi (Hisse Volatilitesi)": 0.24,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.16, "MOVE Endeksi (Tahvil Volatilitesi)": 0.14,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.10, "Dolar Endeksi Zayıflığı (DXY)": 0.04,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.02, "10Y Breakeven Enflasyon İvmesi": 0.01,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.005, "Öncü İstihdam (ICSA)": 0.002,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.001, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            5: {
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.28, "VIX Endeksi (Hisse Volatilitesi)": 0.18,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.16, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.14,
                "Dolar Endeksi Zayıflığı (DXY)": 0.12, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.06,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.03, "10Y Breakeven Enflasyon İvmesi": 0.015,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.01, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.003,
                "Öncü İstihdam (ICSA)": 0.001, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.001
            },
            0: {
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.18, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.18,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.14, "VIX Endeksi (Hisse Volatilitesi)": 0.12,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.10, "MOVE Endeksi (Tahvil Volatilitesi)": 0.10,
                "Dolar Endeksi Zayıflığı (DXY)": 0.08, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.04,
                "10Y Breakeven Enflasyon İvmesi": 0.02, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.02,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.01, "Öncü İstihdam (ICSA)": 0.01
            }
        }
    },

    "S&P 500 (SPX)": {
        "continuum": {
            "Yüksek Getirili Kredi Stresi (HY OAS)": {"GOLDILOCKS": 0.16, "REFLASYON": 0.12, "STAGFLASYON": 0.16, "DEFLASYON": 0.20},
            "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.10, "DEFLASYON": 0.12},
            "VIX Endeksi (Hisse Volatilitesi)": {"GOLDILOCKS": 0.12, "REFLASYON": 0.10, "STAGFLASYON": 0.14, "DEFLASYON": 0.16},
            "Öncü İstihdam (ICSA)": {"GOLDILOCKS": 0.12, "REFLASYON": 0.08, "STAGFLASYON": 0.10, "DEFLASYON": 0.14},
            "Reel Faiz İndirgeme İvmesi (10Y TIPS)": {"GOLDILOCKS": 0.14, "REFLASYON": 0.10, "STAGFLASYON": 0.14, "DEFLASYON": 0.12},
            "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": {"GOLDILOCKS": 0.10, "REFLASYON": 0.08, "STAGFLASYON": 0.10, "DEFLASYON": 0.12},
            "Dolar Endeksi Zayıflığı (DXY)": {"GOLDILOCKS": 0.08, "REFLASYON": 0.12, "STAGFLASYON": 0.08, "DEFLASYON": 0.04},
            "10Y Breakeven Enflasyon İvmesi": {"GOLDILOCKS": 0.04, "REFLASYON": 0.12, "STAGFLASYON": 0.08, "DEFLASYON": 0.02},
            "MOVE Endeksi (Tahvil Volatilitesi)": {"GOLDILOCKS": 0.04, "REFLASYON": 0.04, "STAGFLASYON": 0.06, "DEFLASYON": 0.06},
            "Hazine Nakit / Banka Rezervleri (WRESBAL)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.04, "STAGFLASYON": 0.02, "DEFLASYON": 0.01},
            "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.02, "STAGFLASYON": 0.01, "DEFLASYON": 0.005},
            "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": {"GOLDILOCKS": 0.01, "REFLASYON": 0.02, "STAGFLASYON": 0.01, "DEFLASYON": 0.005}
        },
        "deterministic": {
            1: {
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.22, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.20,
                "10Y Breakeven Enflasyon İvmesi": 0.16, "Öncü İstihdam (ICSA)": 0.14,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.12, "VIX Endeksi (Hisse Volatilitesi)": 0.08,
                "Dolar Endeksi Zayıflığı (DXY)": 0.04, "MOVE Endeksi (Tahvil Volatilitesi)": 0.02,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.01, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.005,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.003, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.002
            },
            2: {
                "VIX Endeksi (Hisse Volatilitesi)": 0.28, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.24,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.16, "MOVE Endeksi (Tahvil Volatilitesi)": 0.14,
                "Dolar Endeksi Zayıflığı (DXY)": 0.10, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.04,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.02, "Öncü İstihdam (ICSA)": 0.01,
                "10Y Breakeven Enflasyon İvmesi": 0.005, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.002,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.002, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.001
            },
            3: {
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.28, "MOVE Endeksi (Tahvil Volatilitesi)": 0.20,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.18, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.14,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.10, "VIX Endeksi (Hisse Volatilitesi)": 0.05,
                "Dolar Endeksi Zayıflığı (DXY)": 0.03, "Öncü İstihdam (ICSA)": 0.01,
                "10Y Breakeven Enflasyon İvmesi": 0.005, "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.002,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.002, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            4: {
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.32, "VIX Endeksi (Hisse Volatilitesi)": 0.24,
                "Öncü İstihdam (ICSA)": 0.16, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.12,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.10, "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.04,
                "Dolar Endeksi Zayıflığı (DXY)": 0.01, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.005,
                "10Y Breakeven Enflasyon İvmesi": 0.002, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.001, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            5: {
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.24, "VIX Endeksi (Hisse Volatilitesi)": 0.18,
                "Öncü İstihdam (ICSA)": 0.16, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.14,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.12, "Dolar Endeksi Zayıflığı (DXY)": 0.08,
                "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.04, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.02,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.01, "10Y Breakeven Enflasyon İvmesi": 0.005,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.002, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.001
            },
            0: {
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.16, "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.16,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.14, "VIX Endeksi (Hisse Volatilitesi)": 0.12,
                "Öncü İstihdam (ICSA)": 0.12, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.10,
                "Dolar Endeksi Zayıflığı (DXY)": 0.08, "10Y Breakeven Enflasyon İvmesi": 0.04,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.04, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.02,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.01, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.01
            }
        }
    },

    "Kripto (BTC)": {
        "continuum": {
            "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": {"GOLDILOCKS": 0.26, "REFLASYON": 0.24, "STAGFLASYON": 0.14, "DEFLASYON": 0.16},
            "Dolar Endeksi Zayıflığı (DXY)": {"GOLDILOCKS": 0.22, "REFLASYON": 0.20, "STAGFLASYON": 0.16, "DEFLASYON": 0.12},
            "Reel Faiz İndirgeme İvmesi (10Y TIPS)": {"GOLDILOCKS": 0.16, "REFLASYON": 0.12, "STAGFLASYON": 0.16, "DEFLASYON": 0.18},
            "VIX Endeksi (Hisse Volatilitesi)": {"GOLDILOCKS": 0.12, "REFLASYON": 0.10, "STAGFLASYON": 0.14, "DEFLASYON": 0.16},
            "Hazine Nakit / Banka Rezervleri (WRESBAL)": {"GOLDILOCKS": 0.10, "REFLASYON": 0.12, "STAGFLASYON": 0.08, "DEFLASYON": 0.06},
            "Yüksek Getirili Kredi Stresi (HY OAS)": {"GOLDILOCKS": 0.06, "REFLASYON": 0.06, "STAGFLASYON": 0.10, "DEFLASYON": 0.12},
            "10Y Breakeven Enflasyon İvmesi": {"GOLDILOCKS": 0.02, "REFLASYON": 0.08, "STAGFLASYON": 0.10, "DEFLASYON": 0.04},
            "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.04, "STAGFLASYON": 0.06, "DEFLASYON": 0.08},
            "MOVE Endeksi (Tahvil Volatilitesi)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.02, "STAGFLASYON": 0.03, "DEFLASYON": 0.04},
            "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": {"GOLDILOCKS": 0.01, "REFLASYON": 0.01, "STAGFLASYON": 0.01, "DEFLASYON": 0.02},
            "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": {"GOLDILOCKS": 0.005, "REFLASYON": 0.005, "STAGFLASYON": 0.01, "DEFLASYON": 0.01},
            "Öncü İstihdam (ICSA)": {"GOLDILOCKS": 0.005, "REFLASYON": 0.005, "STAGFLASYON": 0.01, "DEFLASYON": 0.01}
        },
        "deterministic": {
            1: {
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.24, "Dolar Endeksi Zayıflığı (DXY)": 0.22,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.18, "10Y Breakeven Enflasyon İvmesi": 0.16,
                "VIX Endeksi (Hisse Volatilitesi)": 0.10, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.06,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.02, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.01,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.005, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.003,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001, "Öncü İstihdam (ICSA)": 0.001
            },
            2: {
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.28, "VIX Endeksi (Hisse Volatilitesi)": 0.22,
                "Dolar Endeksi Zayıflığı (DXY)": 0.20, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.16,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.08, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.04,
                "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.015, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.002,
                "10Y Breakeven Enflasyon İvmesi": 0.001, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.0005, "Öncü İstihdam (ICSA)": 0.0005
            },
            3: {
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.30, "Dolar Endeksi Zayıflığı (DXY)": 0.24,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.18, "MOVE Endeksi (Tahvil Volatilitesi)": 0.14,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.08, "VIX Endeksi (Hisse Volatilitesi)": 0.04,
                "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.015, "10Y Breakeven Enflasyon İvmesi": 0.002,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.001, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.0005, "Öncü İstihdam (ICSA)": 0.0005
            },
            4: {
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.28, "VIX Endeksi (Hisse Volatilitesi)": 0.24,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.20, "Dolar Endeksi Zayıflığı (DXY)": 0.16,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.08, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.03,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.005, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.002,
                "10Y Breakeven Enflasyon İvmesi": 0.001, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.0005, "Öncü İstihdam (ICSA)": 0.0005
            },
            5: {
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.34, "Dolar Endeksi Zayıflığı (DXY)": 0.22,
                "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.16, "VIX Endeksi (Hisse Volatilitesi)": 0.14,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.08, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.04,
                "10Y Breakeven Enflasyon İvmesi": 0.015, "MOVE Endeksi (Tahvil Volatilitesi)": 0.002,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.001, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.0005, "Öncü İstihdam (ICSA)": 0.0005
            },
            0: {
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.24, "Dolar Endeksi Zayıflığı (DXY)": 0.20,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.16, "VIX Endeksi (Hisse Volatilitesi)": 0.14,
                "HY OAS": 0.10, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.08,
                "10Y Breakeven Enflasyon İvmesi": 0.03, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.02,
                "MOVE": 0.015, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.005,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.005, "Öncü İstihdam (ICSA)": 0.005
            }
        }
    },

    "Ham Petrol (WTI)": {
        "continuum": {
            "10Y Breakeven Enflasyon İvmesi": {"GOLDILOCKS": 0.16, "REFLASYON": 0.26, "STAGFLASYON": 0.24, "DEFLASYON": 0.08},
            "Dolar Endeksi Zayıflığı (DXY)": {"GOLDILOCKS": 0.18, "REFLASYON": 0.18, "STAGFLASYON": 0.16, "DEFLASYON": 0.10},
            "Öncü İstihdam (ICSA)": {"GOLDILOCKS": 0.16, "REFLASYON": 0.14, "STAGFLASYON": 0.12, "DEFLASYON": 0.20},
            "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": {"GOLDILOCKS": 0.16, "REFLASYON": 0.14, "STAGFLASYON": 0.10, "DEFLASYON": 0.08},
            "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": {"GOLDILOCKS": 0.10, "REFLASYON": 0.16, "STAGFLASYON": 0.18, "DEFLASYON": 0.04},
            "Yüksek Getirili Kredi Stresi (HY OAS)": {"GOLDILOCKS": 0.08, "REFLASYON": 0.04, "STAGFLASYON": 0.08, "DEFLASYON": 0.18},
            "Reel Faiz İndirgeme İvmesi (10Y TIPS)": {"GOLDILOCKS": 0.06, "REFLASYON": 0.04, "STAGFLASYON": 0.06, "DEFLASYON": 0.12},
            "VIX Endeksi (Hisse Volatilitesi)": {"GOLDILOCKS": 0.04, "REFLASYON": 0.01, "STAGFLASYON": 0.02, "DEFLASYON": 0.08},
            "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.01, "STAGFLASYON": 0.02, "DEFLASYON": 0.06},
            "Hazine Nakit / Banka Rezervleri (WRESBAL)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.01, "STAGFLASYON": 0.01, "DEFLASYON": 0.02},
            "MOVE Endeksi (Tahvil Volatilitesi)": {"GOLDILOCKS": 0.01, "REFLASYON": 0.005, "STAGFLASYON": 0.005, "DEFLASYON": 0.02},
            "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": {"GOLDILOCKS": 0.01, "REFLASYON": 0.005, "STAGFLASYON": 0.005, "DEFLASYON": 0.02}
        },
        "deterministic": {
            1: {
                "10Y Breakeven Enflasyon İvmesi": 0.28, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.20,
                "Öncü İstihdam (ICSA)": 0.16, "Dolar Endeksi Zayıflığı (DXY)": 0.16,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.12, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.04,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.02, "VIX Endeksi (Hisse Volatilitesi)": 0.01,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.005, "MOVE Endeksi (Tahvil Volatilitesi)": 0.002,
                "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.002, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001
            },
            2: {
                "Dolar Endeksi Zayıflığı (DXY)": 0.26, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.20,
                "Öncü İstihdam (ICSA)": 0.18, "VIX Endeksi (Hisse Volatilitesi)": 0.16,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.12, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.04,
                "10Y Breakeven Enflasyon İvmesi": 0.02, "MOVE Endeksi (Tahvil Volatilitesi)": 0.01,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.005, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.002,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.002, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001
            },
            3: {
                "Dolar Endeksi Zayıflığı (DXY)": 0.26, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.20,
                "Öncü İstihdam (ICSA)": 0.18, "10Y Breakeven Enflasyon İvmesi": 0.16,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.10, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.04,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.03, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.015,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.01, "VIX Endeksi (Hisse Volatilitesi)": 0.002,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.002, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            4: {
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.28, "Öncü İstihdam (ICSA)": 0.24,
                "Dolar Endeksi Zayıflığı (DXY)": 0.18, "VIX Endeksi (Hisse Volatilitesi)": 0.16,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.08, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.03,
                "10Y Breakeven Enflasyon İvmesi": 0.015, "MOVE Endeksi (Tahvil Volatilitesi)": 0.01,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.002, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.001,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            5: {
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.24, "Dolar Endeksi Zayıflığı (DXY)": 0.20,
                "Öncü İstihdam (ICSA)": 0.18, "10Y Breakeven Enflasyon İvmesi": 0.16,
                "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.12, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.05,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.025, "VIX Endeksi (Hisse Volatilitesi)": 0.01,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.01, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.002,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.002, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001
            },
            0: {
                "10Y Breakeven Enflasyon İvmesi": 0.18, "Dolar Endeksi Zayıflığı (DXY)": 0.16,
                "Öncü İstihdam (ICSA)": 0.16, "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.14,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.12, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.10,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.06, "VIX Endeksi (Hisse Volatilitesi)": 0.04,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.02, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.01,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.005, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.005
            }
        }
    },

    "Bakır (HG)": {
        "continuum": {
            "Öncü İstihdam (ICSA)": {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.14, "DEFLASYON": 0.22},
            "Dolar Endeksi Zayıflığı (DXY)": {"GOLDILOCKS": 0.18, "REFLASYON": 0.18, "STAGFLASYON": 0.14, "DEFLASYON": 0.10},
            "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": {"GOLDILOCKS": 0.16, "REFLASYON": 0.16, "STAGFLASYON": 0.10, "DEFLASYON": 0.08},
            "Yüksek Getirili Kredi Stresi (HY OAS)": {"GOLDILOCKS": 0.12, "REFLASYON": 0.06, "STAGFLASYON": 0.12, "DEFLASYON": 0.18},
            "10Y Breakeven Enflasyon İvmesi": {"GOLDILOCKS": 0.10, "REFLASYON": 0.20, "STAGFLASYON": 0.18, "DEFLASYON": 0.06},
            "Reel Faiz İndirgeme İvmesi (10Y TIPS)": {"GOLDILOCKS": 0.10, "REFLASYON": 0.06, "STAGFLASYON": 0.10, "DEFLASYON": 0.12},
            "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": {"GOLDILOCKS": 0.06, "REFLASYON": 0.10, "STAGFLASYON": 0.12, "DEFLASYON": 0.04},
            "VIX Endeksi (Hisse Volatilitesi)": {"GOLDILOCKS": 0.04, "REFLASYON": 0.02, "STAGFLASYON": 0.04, "DEFLASYON": 0.08},
            "Hazine Nakit / Banka Rezervleri (WRESBAL)": {"GOLDILOCKS": 0.03, "REFLASYON": 0.03, "STAGFLASYON": 0.02, "DEFLASYON": 0.01},
            "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.01, "STAGFLASYON": 0.02, "DEFLASYON": 0.04},
            "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": {"GOLDILOCKS": 0.005, "REFLASYON": 0.01, "STAGFLASYON": 0.01, "DEFLASYON": 0.02},
            "MOVE Endeksi (Tahvil Volatilitesi)": {"GOLDILOCKS": 0.005, "REFLASYON": 0.01, "STAGFLASYON": 0.01, "DEFLASYON": 0.02}
        },
        "deterministic": {
            1: {
                "10Y Breakeven Enflasyon İvmesi": 0.24, "Öncü İstihdam (ICSA)": 0.20,
                "Dolar Endeksi Zayıflığı (DXY)": 0.18, "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.16,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.12, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.04,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.03, "VIX Endeksi (Hisse Volatilitesi)": 0.01,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.01, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.005,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.003, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.002
            },
            2: {
                "Dolar Endeksi Zayıflığı (DXY)": 0.28, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.22,
                "Öncü İstihdam (ICSA)": 0.18, "VIX Endeksi (Hisse Volatilitesi)": 0.14,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.12, "MOVE Endeksi (Tahvil Volatilitesi)": 0.03,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.015, "10Y Breakeven Enflasyon İvmesi": 0.008,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.004, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.001, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001
            },
            3: {
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.26, "Dolar Endeksi Zayıflığı (DXY)": 0.22,
                "Öncü İstihdam (ICSA)": 0.18, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.16,
                "10Y Breakeven Enflasyon İvmesi": 0.10, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.04,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.02, "MOVE Endeksi (Tahvil Volatilitesi)": 0.01,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.005, "VIX Endeksi (Hisse Volatilitesi)": 0.002,
                "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.002, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001
            },
            4: {
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.30, "Öncü İstihdam (ICSA)": 0.24,
                "Dolar Endeksi Zayıflığı (DXY)": 0.18, "VIX Endeksi (Hisse Volatilitesi)": 0.14,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.08, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.03,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.015, "10Y Breakeven Enflasyon İvmesi": 0.008,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.004, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.001,
                "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001
            },
            5: {
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.26, "Dolar Endeksi Zayıflığı (DXY)": 0.22,
                "Öncü İstihdam (ICSA)": 0.18, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.14,
                "10Y Breakeven Enflasyon İvmesi": 0.12, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.04,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.02, "VIX Endeksi (Hisse Volatilitesi)": 0.01,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.005, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.002,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.002, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.001
            },
            0: {
                "Öncü İstihdam (ICSA)": 0.18, "Dolar Endeksi Zayıflığı (DXY)": 0.18,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.16, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.14,
                "10Y Breakeven Enflasyon İvmesi": 0.12, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.10,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.05, "VIX Endeksi (Hisse Volatilitesi)": 0.03,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.02, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.01,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.005, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.005
            }
        }
    },

    "ABD Tahvili / Faiz (TLT)": {
        "continuum": {
            "Reel Faiz İndirgeme İvmesi (10Y TIPS)": {"GOLDILOCKS": 0.22, "REFLASYON": 0.18, "STAGFLASYON": 0.22, "DEFLASYON": 0.24},
            "10Y Breakeven Enflasyon İvmesi": {"GOLDILOCKS": 0.16, "REFLASYON": 0.22, "STAGFLASYON": 0.20, "DEFLASYON": 0.10},
            "MOVE Endeksi (Tahvil Volatilitesi)": {"GOLDILOCKS": 0.14, "REFLASYON": 0.12, "STAGFLASYON": 0.16, "DEFLASYON": 0.18},
            "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": {"GOLDILOCKS": 0.14, "REFLASYON": 0.10, "STAGFLASYON": 0.12, "DEFLASYON": 0.18},
            "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": {"GOLDILOCKS": 0.12, "REFLASYON": 0.10, "STAGFLASYON": 0.10, "DEFLASYON": 0.14},
            "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": {"GOLDILOCKS": 0.08, "REFLASYON": 0.14, "STAGFLASYON": 0.10, "DEFLASYON": 0.04},
            "Yüksek Getirili Kredi Stresi (HY OAS)": {"GOLDILOCKS": 0.06, "REFLASYON": 0.04, "STAGFLASYON": 0.04, "DEFLASYON": 0.06},
            "Dolar Endeksi Zayıflığı (DXY)": {"GOLDILOCKS": 0.04, "REFLASYON": 0.04, "STAGFLASYON": 0.02, "DEFLASYON": 0.02},
            "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": {"GOLDILOCKS": 0.02, "REFLASYON": 0.03, "STAGFLASYON": 0.02, "DEFLASYON": 0.02},
            "VIX Endeksi (Hisse Volatilitesi)": {"GOLDILOCKS": 0.01, "REFLASYON": 0.01, "STAGFLASYON": 0.01, "DEFLASYON": 0.01},
            "Öncü İstihdam (ICSA)": {"GOLDILOCKS": 0.005, "REFLASYON": 0.01, "STAGFLASYON": 0.005, "DEFLASYON": 0.005},
            "Hazine Nakit / Banka Rezervleri (WRESBAL)": {"GOLDILOCKS": 0.005, "REFLASYON": 0.01, "STAGFLASYON": 0.005, "DEFLASYON": 0.005}
        },
        "deterministic": {
            1: {
                "10Y Breakeven Enflasyon İvmesi": 0.26, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.22,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.20, "MOVE Endeksi (Tahvil Volatilitesi)": 0.16,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.10, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.04,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.01, "Dolar Endeksi Zayıflığı (DXY)": 0.005,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.002, "VIX Endeksi (Hisse Volatilitesi)": 0.001,
                "Öncü İstihdam (ICSA)": 0.001, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            2: {
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.28, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.22,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.18, "VIX Endeksi (Hisse Volatilitesi)": 0.16,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.10, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.04,
                "Dolar Endeksi Zayıflığı (DXY)": 0.01, "10Y Breakeven Enflasyon İvmesi": 0.005,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.002, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.001,
                "Öncü İstihdam (ICSA)": 0.001, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            3: {
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.36, "MOVE Endeksi (Tahvil Volatilitesi)": 0.22,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.16, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.14,
                "Dolar Endeksi Zayıflığı (DXY)": 0.08, "10Y Breakeven Enflasyon İvmesi": 0.02,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.01, "Yüksek Getirili Kredi Stresi (HY OAS)": 0.005,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.002, "VIX Endeksi (Hisse Volatilitesi)": 0.001,
                "Öncü İstihdam (ICSA)": 0.001, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            4: {
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.26, "MOVE Endeksi (Tahvil Volatilitesi)": 0.24,
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.20, "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.16,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.10, "VIX Endeksi (Hisse Volatilitesi)": 0.02,
                "10Y Breakeven Enflasyon İvmesi": 0.01, "Dolar Endeksi Zayıflığı (DXY)": 0.005,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.002, "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.001,
                "Öncü İstihdam (ICSA)": 0.001, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.001
            },
            5: {
                "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.24, "MOVE Endeksi (Tahvil Volatilitesi)": 0.20,
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.18, "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.16,
                "10Y Breakeven Enflasyon İvmesi": 0.12, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.05,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.03, "Dolar Endeksi Zayıflığı (DXY)": 0.01,
                "Yüksek Getirili Kredi Stresi (HY OAS)": 0.005, "VIX Endeksi (Hisse Volatilitesi)": 0.002,
                "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.002, "Öncü İstihdam (ICSA)": 0.001
            },
            0: {
                "Reel Faiz İndirgeme İvmesi (10Y TIPS)": 0.22, "10Y Breakeven Enflasyon İvmesi": 0.18,
                "MOVE Endeksi (Tahvil Volatilitesi)": 0.16, "Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)": 0.16,
                "Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)": 0.12, "HY OAS": 0.08,
                "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)": 0.04, "Dolar Endeksi Zayıflığı (DXY)": 0.02,
                "G4 Küresel Süper Likidite (Fed+ECB+BoJ)": 0.01, "VIX Endeksi (Hisse Volatilitesi)": 0.005,
                "Öncü İstihdam (ICSA)": 0.003, "Hazine Nakit / Banka Rezervleri (WRESBAL)": 0.002
            }
        }
    }
}


def get_dynamic_asset_weights(
    asset_name: str,
    confirmed_regime_id: int,
    regime_probs: Dict[str, float],
    in_transition: bool = False
) -> Dict[str, float]:
    """
    Computes mathematically aligned, normalized weights for the 12 macro indicators.
    Dynamically balances between Continuum probabilities and Active Deterministic Regime.
    """
    asset_cfg = ASSET_REGIME_CONFIGS.get(asset_name, ASSET_REGIME_CONFIGS["Altın (XAU)"])
    cont_spec = asset_cfg["continuum"]
    det_spec = asset_cfg["deterministic"]
    
    # 1. Compute continuum blended weight for each indicator
    continuum_weights = {}
    for ind_name in INDICATORS:
        reg_dict = cont_spec.get(ind_name, {})
        w_c = sum(regime_probs.get(r, 0.25) * reg_dict.get(r, 0.08) for r in regime_probs)
        continuum_weights[ind_name] = w_c
        
    # 2. Determine deterministic regime blending factor (alpha)
    # If confirmed regime is in [1, 2, 3, 4, 5], strong shock/rally weight is applied.
    # If in transition (pending hysteresis), smoothly blend at 45%; when locked, blend at 75%.
    if confirmed_regime_id in [1, 2, 3, 4, 5]:
        alpha = 0.45 if in_transition else 0.75
        det_weights = det_spec.get(confirmed_regime_id, det_spec.get(0, {}))
    else:
        alpha = 0.0 # Pure continuum baseline
        det_weights = det_spec.get(0, {})
        
    # 3. Dynamic synthesis
    blended_weights = {}
    for ind_name in INDICATORS:
        w_cont = continuum_weights.get(ind_name, 0.08)
        w_det = det_weights.get(ind_name, 0.08)
        w_final = (1.0 - alpha) * w_cont + alpha * w_det
        blended_weights[ind_name] = max(0.001, w_final)
        
    # 4. Strict normalization to sum to 1.0
    total_w = sum(blended_weights.values())
    normalized_weights = {k: v / total_w for k, v in blended_weights.items()}
    return normalized_weights


def get_asset_regime_weight_matrix(asset_name: str) -> pd.DataFrame:
    """
    Returns the complete calibrated weight matrix across all regimes for the asset.
    Useful for UI displays, audits, and transparency.
    """
    asset_cfg = ASSET_REGIME_CONFIGS.get(asset_name, ASSET_REGIME_CONFIGS["Altın (XAU)"])
    det_spec = asset_cfg["deterministic"]
    
    regime_columns = {
        0: "Geçiş / Nötr",
        1: "R1: Enflasyon Şoku",
        2: "R2: Likidite Şoku",
        3: "R3: Reel Faiz Şoku",
        4: "R4: Kredi Temerrüdü",
        5: "R5: Likidite Rallisi"
    }
    
    rows = []
    for ind in INDICATORS:
        row = {"Makro Gösterge": ind}
        for r_id, col_name in regime_columns.items():
            r_weights = det_spec.get(r_id, {})
            tot = sum(r_weights.values()) if sum(r_weights.values()) > 0 else 1.0
            val = r_weights.get(ind, 0.0) / tot
            row[col_name] = f"%{val * 100:.1f}"
        rows.append(row)
        
    return pd.DataFrame(rows)
