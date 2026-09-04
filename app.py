import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from fredapi import Fred
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. SAYFA VE API AYARLARI ---
st.set_page_config(page_title="Makro Trend v25.0 (Upstream Macro Master)", layout="wide")

try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=FRED_API_KEY)
except:
    st.error("Lütfen Streamlit Cloud ayarlarına FRED_API_KEY eklediğinizden emin olun!")
    st.stop()

# --- 2. GELİŞMİŞ VERİ VE LİKİDİTE MOTORLARI ---
@st.cache_data(ttl=1800)
def fetch_fred_data(series_id, days=2500):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    try:
        data = fred.get_series(series_id, start_date, end_date)
        s = pd.Series(data)
        s.index = pd.to_datetime(s.index)
        s = s.resample('B').ffill().bfill().dropna()
        return s.astype(float)
    except:
        return pd.Series(dtype=float)

@st.cache_data(ttl=1800)
def fetch_yf_data(ticker, days=2500):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    try:
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if data.empty:
            data = yf.download(ticker, period="10y", progress=False)
            
        if data.empty:
            return pd.Series(dtype=float)
            
        if 'Close' in data.columns:
            s = data['Close']
        else:
            s = data.iloc[:, 0]
            
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
            
        s = pd.Series(s.values.flatten(), index=pd.to_datetime(s.index))
        if s.index.tz is not None:
            s.index = s.index.tz_localize(None)
        s = s.resample('B').ffill().bfill().dropna()
        return s.astype(float)
    except:
        return pd.Series(dtype=float)

# ZIRHLI RASYONEL VE MAKAS HESAPLAYICI
def safe_ratio(s1, s2):
    if s1.empty or s2.empty:
        return pd.Series(dtype=float)
    df = pd.concat([s1, s2], axis=1).ffill().bfill().dropna()
    if df.empty or len(df.columns) < 2:
        return pd.Series(dtype=float)
    ratio = df.iloc[:, 0] / (df.iloc[:, 1] + 1e-6)
    return ratio.dropna()

def safe_spread(s1, s2):
    if s1.empty or s2.empty:
        return pd.Series(dtype=float)
    df = pd.concat([s1, s2], axis=1).ffill().bfill().dropna()
    if df.empty or len(df.columns) < 2:
        return pd.Series(dtype=float)
    spread = df.iloc[:, 0] - df.iloc[:, 1]
    return spread.dropna()

# DEFİLLAMA STABLECOIN KÜRESEL ARZ MOTORU
@st.cache_data(ttl=1800)
def fetch_defillama_stablecoins():
    try:
        url = "https://stablecoins.llama.fi/stablecoincharts/all"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            records = []
            for item in data:
                ts = int(item.get('date', 0))
                mcap = float(item.get('totalCirculating', {}).get('peggedUSD', 0))
                if ts > 0 and mcap > 0:
                    records.append({'date': pd.to_datetime(ts, unit='s'), 'mcap': mcap})
            if records:
                df = pd.DataFrame(records).set_index('date').sort_index()
                s = df['mcap'].resample('B').ffill().bfill().dropna()
                return s.astype(float)
    except:
        pass
    return pd.Series(dtype=float)

# ALTERNATIVE.ME KRİPTO KORKU & AÇGÖZLÜLÜK ENDEKSİ
@st.cache_data(ttl=1800)
def fetch_crypto_fear_greed():
    try:
        url = "https://api.alternative.me/fng/?limit=2000&format=json"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json().get('data', [])
            records = []
            for item in data:
                ts = int(item.get('timestamp', 0))
                val = float(item.get('value', 50))
                if ts > 0:
                    records.append({'date': pd.to_datetime(ts, unit='s'), 'val': val})
            if records:
                df = pd.DataFrame(records).set_index('date').sort_index()
                s = df['val'].resample('B').ffill().bfill().dropna()
                return s.astype(float)
    except:
        pass
    return pd.Series(dtype=float)

# G4 KONSOLİDE KÜRESEL LİKİDİTE MOTORU
@st.cache_data(ttl=1800)
def fetch_g4_global_net_liquidity(days=2500):
    try:
        walcl = fetch_fred_data('WALCL', days)       
        tga = fetch_fred_data('WTREGEN', days)       
        rrp = fetch_fred_data('RRPONTSYD', days)     
        ecb = fetch_fred_data('ECBASSETSW', days)   
        eurusd = fetch_yf_data('EURUSD=X', days)     
        usdjpy = fetch_yf_data('JPY=X', days)       
        
        df = pd.concat([walcl, tga, rrp, ecb, eurusd, usdjpy], axis=1).ffill().bfill().dropna()
        if df.empty or len(df.columns) < 6:
            return fetch_fred_data('WALCL', days)
        
        w = df.iloc[:, 0]
        t = df.iloc[:, 1]
        r = df.iloc[:, 2] * 1000.0
        e = df.iloc[:, 3]
        eur = df.iloc[:, 4]
        jpy = df.iloc[:, 5]
        
        us_net = w - t - r
        ecb_usd = e * eur
        boj_impulse = (jpy / (jpy.rolling(252, min_periods=30).mean() + 1e-5)) * 2000000.0
        
        g4_total = us_net + (ecb_usd * 0.35) + (boj_impulse * 0.25)
        return g4_total.dropna().astype(float)
    except:
        return fetch_fred_data('WALCL', days)

# --- 3. BİRLEŞİK REJİM MOTORU ---
def get_realtime_macro_regime():
    t10yie = fetch_fred_data('T10YIE') 
    real_rate = fetch_fred_data('DFII10') 
    icsa = fetch_fred_data('ICSA') 
    nfci = fetch_fred_data('NFCI')
    vix = fetch_yf_data('^VIX')
    hy_oas = fetch_fred_data('BAMLH0A0HYM2')
    
    if len(t10yie) < 60 or len(real_rate) < 60:
        return "NOTR", "NÖTR PİYASA", 1.0, 2.30
        
    lookback_inf = min(len(t10yie), 504)
    inf_dynamic_anchor = float(t10yie.tail(lookback_inf).mean() + (0.25 * t10yie.tail(lookback_inf).std()))
    
    loose_financial_conditions = (not nfci.empty and nfci.iloc[-1] < -0.30) and (not hy_oas.empty and hy_oas.iloc[-1] < 3.20)
    market_calm = not vix.empty and vix.iloc[-1] < 18.0
    
    lookback_icsa = min(len(icsa), 130)
    labor_deteriorating = (not icsa.empty) and (icsa.iloc[-1] > float(icsa.tail(lookback_icsa).quantile(0.70)))
    inf_pressure = t10yie.iloc[-1] > inf_dynamic_anchor and not market_calm

    if loose_financial_conditions and not labor_deteriorating and not inf_pressure:
        return "GOLDILOCKS", "GOLDILOCKS (Gevşek Finansal Koşullar, Canlı Büyüme)", 1.25, inf_dynamic_anchor
    elif not labor_deteriorating:
        return "REFLASYON", "REFLASYON (Genişleyen Büyüme & Emtia Talebi)", 1.15, inf_dynamic_anchor
    elif inf_pressure and labor_deteriorating:
        return "STAGFLASYON", "STAGFLASYON (Yapışkan Enflasyon, Zayıflayan İstihdam)", 1.40, inf_dynamic_anchor
    else:
        return "DEFLASYON", "DEFLASYONİST DARALMA (Çöken Kredi, Resesyon Baskısı)", 1.40, inf_dynamic_anchor

# --- 4. OTONOM ŞALTER MOTORU ---
def check_systemic_circuit_breaker():
    move = fetch_yf_data('^MOVE')
    hy_oas = fetch_fred_data('BAMLH0A0HYM2') 
    nfci = fetch_fred_data('NFCI')
    vix = fetch_yf_data('^VIX')
    
    reasons = []
    is_triggered = False
    
    if not move.empty and len(move) > 60:
        move_dyn_thresh = max(120.0, float(move.tail(504).quantile(0.96)))
        if move.iloc[-1] > move_dyn_thresh:
            is_triggered = True
            reasons.append(f"MOVE Tahvil Volatilitesi Dinamik Risk Eşiğinde ({move.iloc[-1]:.1f} > {move_dyn_thresh:.1f})")
        
    if not hy_oas.empty and len(hy_oas) > 60:
        hy_dyn_thresh = max(4.5, float(hy_oas.tail(504).quantile(0.96)))
        if hy_oas.iloc[-1] > hy_dyn_thresh:
            is_triggered = True
            reasons.append(f"Yüksek Getirili Kredi (HY Spread) Dinamik Stres Eşiğinde ({hy_oas.iloc[-1]:.2f}%)")
            
    if not nfci.empty and len(nfci) > 50:
        nfci_dyn_thresh = max(0.05, float(nfci.tail(252).quantile(0.92)))
        if nfci.iloc[-1] > nfci_dyn_thresh:
            is_triggered = True
            reasons.append(f"Chicago Fed NFCI Sıkılaşma Eşiğinde ({nfci.iloc[-1]:.2f} > {nfci_dyn_thresh:.2f})")
        
    if not vix.empty and len(vix) > 60:
        vix_dyn_thresh = max(28.0, float(vix.tail(504).quantile(0.96)))
        if vix.iloc[-1] > vix_dyn_thresh:
            is_triggered = True
            reasons.append(f"VIX Panik Eşiğinde ({vix.iloc[-1]:.1f} > {vix_dyn_thresh:.1f})")
        
    return is_triggered, reasons

# --- 5. BİRLEŞİK EKONOMETRİK Z-SKOR MOTORU ---
def process_indicator(data_series, invert=False):
    if isinstance(data_series, pd.DataFrame):
        data_series = data_series.iloc[:, 0]
        
    data_series = data_series.dropna()
    
    if len(data_series) < 30:
        val = float(data_series.iloc[-1]) if not data_series.empty else 0.0
        return 0.0, val
    
    current_val = float(data_series.iloc[-1])
    
    lookback = min(len(data_series), 252)
    ema_trend = data_series.ewm(span=40, adjust=False).mean().iloc[-1]
    mean_baseline = data_series.tail(lookback).mean()
    std_baseline = data_series.tail(lookback).std()
    
    base_z = (ema_trend - mean_baseline) / (std_baseline + 1e-5)
    
    if invert:
        base_z = -base_z
        
    z_score = float(max(-2.5, min(2.5, base_z)))
    return z_score, current_val

# --- 6. ARAYÜZ VE UYGULAMA ---
st.title("🏛️ KÜRESEL MAKRO MODELİ (v25.0 - UPSTREAM MACRO MASTER)")
st.markdown("**Saf Makro & Likidite Plumbing Hiyerarşisi — Fiyat Türevleri Dipte, Makro Zirvede**")

st.sidebar.header("VARLIK VE RİSK YÖNETİMİ")
asset = st.sidebar.radio("Analiz Edilecek Varlık:", (
    "Altın (XAU)", 
    "Gümüş (XAG)", 
    "Nasdaq 100 (NQ)", 
    "S&P 500 (SPX)",
    "Kripto (BTC)",
    "Ham Petrol (WTI)",
    "Bakır (HG)",
    "ABD Tahvili / Faiz (TLT)"
))

target_vol_input = st.sidebar.slider("Hedef Portföy Volatilitesi (% Target Vol):", min_value=8.0, max_value=25.0, value=12.0, step=1.0)

regime_code, regime_name, regime_multiplier, dynamic_inf_anchor = get_realtime_macro_regime()
circuit_triggered, circuit_reasons = check_systemic_circuit_breaker()

# Üst Bilgi Kartları
col_info1, col_info2, col_info3 = st.columns(3)
with col_info1:
    st.metric("Aktif Piyasa Rejimi (Likidite/Büyüme)", regime_code, f"Çarpan: {regime_multiplier}x")
with col_info2:
    if circuit_triggered:
        st.metric("Sistemik Risk Şalteri", "🚨 AKTİF (KORUMA MODU)", "Risk Azaltıldı", delta_color="inverse")
    else:
        st.metric("Sistemik Risk Şalteri", "✅ NORMAL (OTONOM)", "Dinamik Eşikler Dengeli")
with col_info3:
    t10_val = fetch_fred_data('T10YIE')
    tips_val = fetch_fred_data('DFII10')
    st.metric("10Y Breakeven Enflasyon", f"%{t10_val.iloc[-1]:.2f}" if not t10_val.empty else "N/A", f"10Y Reel Faiz: %{tips_val.iloc[-1]:.2f}" if not tips_val.empty else "N/A")

if circuit_triggered:
    st.error(f"⚠️ **SİSTEMİK RİSK ŞALTERİ DEVREDE:** Aşağıdaki anomaliler sebebiyle alım sinyalleri baskılanmıştır:\n* " + "\n* ".join(circuit_reasons))

indicators_data = []
total_score = 0

with st.spinner(f"{asset} için Saf Makro Hiyerarşi Hesaplanıyor..."):
    
    # Ortak Veri Akışları (Saf Makro Çapaları)
    dgs2 = fetch_fred_data('DGS2')
    effr = fetch_fred_data('EFFR')
    fed_easing_spread = safe_spread(dgs2, effr)
    
    g4_liq = fetch_g4_global_net_liquidity()
    tips_real = fetch_fred_data('DFII10')
    t10yie = fetch_fred_data('T10YIE')
    t5yifr = fetch_fred_data('T5YIFR')
    dxy = fetch_yf_data('DX-Y.NYB')
    bdry = fetch_yf_data('BDRY')
    dgs30 = fetch_fred_data('DGS30')
    icsa = fetch_fred_data('ICSA')
    nfci = fetch_fred_data('NFCI')
    hy_oas = fetch_fred_data('BAMLH0A0HYM2')
    move = fetch_yf_data('^MOVE')
    t10y2y = fetch_fred_data('T10Y2Y')
    wresbal = fetch_fred_data('WRESBAL')
    vix = fetch_yf_data('^VIX')
    dbb = fetch_yf_data('DBB')
    
    # --- TAVİZSİZ UPSTREAM MAKRO HİYERARŞİSİ ---
    # ZİRVEDE (Satır 0-5): G4 Likidite, Breakeven, TIPS Reel Faiz, Easing Spread, NFCI (%75+ Ağırlık)
    # DİPTE (Satır 6+): Sektörel / Fiyat Oranları & Tali Sensörler (%2-%5 Ağırlık)
    
    if asset == "Altın (XAU)":
        gold_oil_ratio = safe_ratio(fetch_yf_data('GC=F'), fetch_yf_data('CL=F'))
        metrics_spec = [
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", g4_liq, {"GOLDILOCKS": 0.22, "REFLASYON": 0.22, "STAGFLASYON": 0.20, "DEFLASYON": 0.22}, False),
            ("10Y Breakeven Enflasyon Genişlemesi", t10yie, {"GOLDILOCKS": 0.20, "REFLASYON": 0.22, "STAGFLASYON": 0.26, "DEFLASYON": 0.10}, False),
            ("Piyasa Faiz İndirim Makası (DGS2 - EFFR)", fed_easing_spread, {"GOLDILOCKS": 0.16, "REFLASYON": 0.16, "STAGFLASYON": 0.12, "DEFLASYON": 0.18}, True),
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", tips_real, {"GOLDILOCKS": 0.14, "REFLASYON": 0.14, "STAGFLASYON": 0.10, "DEFLASYON": 0.16}, True),
            ("Dolar Endeksi Zayıflığı (DXY)", dxy, {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.10, "DEFLASYON": 0.14}, True),
            ("5y5y Forward Enflasyon Çıpası", t5yifr, {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False),
            # Tali / Dip Göstergeler
            ("Küresel Deniz Ticareti/Navlun (BDRY)", bdry, {"GOLDILOCKS": 0.03, "REFLASYON": 0.02, "STAGFLASYON": 0.05, "DEFLASYON": 0.02}, False),
            ("Altın / Petrol Stagflasyon Gücü (GC/CL)", gold_oil_ratio, {"GOLDILOCKS": 0.02, "REFLASYON": 0.02, "STAGFLASYON": 0.04, "DEFLASYON": 0.04}, False),
            ("Ticari Banka Rezervleri (WRESBAL)", wresbal, {"GOLDILOCKS": 0.01, "REFLASYON": 0.01, "STAGFLASYON": 0.02, "DEFLASYON": 0.03}, False),
            ("Endüstriyel Metaller Sepeti (DBB)", dbb, {"GOLDILOCKS": 0.01, "REFLASYON": 0.005, "STAGFLASYON": 0.01, "DEFLASYON": 0.02}, False),
            ("MOVE Endeksi (Tahvil/Jeopolitik Panik)", move, {"GOLDILOCKS": 0.005, "REFLASYON": 0.003, "STAGFLASYON": 0.01, "DEFLASYON": 0.01}, False),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", dgs30, {"GOLDILOCKS": 0.005, "REFLASYON": 0.002, "STAGFLASYON": 0.01, "DEFLASYON": 0.01}, True),
        ]
    elif asset == "Gümüş (XAG)":
        hg_gc_ratio = safe_ratio(fetch_yf_data('HG=F'), fetch_yf_data('GC=F'))
        gc_si_ratio = safe_ratio(fetch_yf_data('GC=F'), fetch_yf_data('SI=F'))
        metrics_spec = [
            # Altın ile %95 Birebir Eşitlenmiş Zirve Parasal Hiyerarşi
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", g4_liq, {"GOLDILOCKS": 0.22, "REFLASYON": 0.22, "STAGFLASYON": 0.20, "DEFLASYON": 0.22}, False),
            ("10Y Breakeven Enflasyon Genişlemesi", t10yie, {"GOLDILOCKS": 0.20, "REFLASYON": 0.22, "STAGFLASYON": 0.26, "DEFLASYON": 0.10}, False),
            ("Piyasa Faiz İndirim Makası (DGS2 - EFFR)", fed_easing_spread, {"GOLDILOCKS": 0.16, "REFLASYON": 0.16, "STAGFLASYON": 0.12, "DEFLASYON": 0.18}, True),
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", tips_real, {"GOLDILOCKS": 0.14, "REFLASYON": 0.14, "STAGFLASYON": 0.10, "DEFLASYON": 0.16}, True),
            ("Dolar Endeksi Zayıflığı (DXY)", dxy, {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.10, "DEFLASYON": 0.14}, True),
            ("5y5y Forward Enflasyon Çıpası", t5yifr, {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False),
            # Tali / Dip Göstergeler
            ("Küresel Deniz Ticareti/Navlun (BDRY)", bdry, {"GOLDILOCKS": 0.03, "REFLASYON": 0.02, "STAGFLASYON": 0.05, "DEFLASYON": 0.02}, False),
            ("Endüstriyel Metaller Sepeti (DBB)", dbb, {"GOLDILOCKS": 0.02, "REFLASYON": 0.02, "STAGFLASYON": 0.03, "DEFLASYON": 0.03}, False),
            ("Bakır / Altın Büyüme Rasyosu (HG/GC)", hg_gc_ratio, {"GOLDILOCKS": 0.01, "REFLASYON": 0.01, "STAGFLASYON": 0.02, "DEFLASYON": 0.02}, False),
            ("Ticari Banka Rezervleri (WRESBAL)", wresbal, {"GOLDILOCKS": 0.01, "REFLASYON": 0.005, "STAGFLASYON": 0.02, "DEFLASYON": 0.03}, False),
            ("Altın / Gümüş Değerleme Rasyosu (GC/SI)", gc_si_ratio, {"GOLDILOCKS": 0.005, "REFLASYON": 0.003, "STAGFLASYON": 0.01, "DEFLASYON": 0.01}, True),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", dgs30, {"GOLDILOCKS": 0.005, "REFLASYON": 0.002, "STAGFLASYON": 0.01, "DEFLASYON": 0.01}, True),
        ]
    elif asset == "Nasdaq 100 (NQ)":
        soxx_qqq_ratio = safe_ratio(fetch_yf_data('SOXX'), fetch_yf_data('QQQ'))
        qqq_tnx_ratio = safe_ratio(fetch_yf_data('QQQ'), fetch_yf_data('^TNX'))
        metrics_spec = [
            # ZİRVE: Saf Kredi Koşulları & Likidite Plumbing (%75+)
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", g4_liq, {"GOLDILOCKS": 0.24, "REFLASYON": 0.22, "STAGFLASYON": 0.16, "DEFLASYON": 0.22}, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", nfci, {"GOLDILOCKS": 0.22, "REFLASYON": 0.20, "STAGFLASYON": 0.16, "DEFLASYON": 0.18}, True),
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", tips_real, {"GOLDILOCKS": 0.16, "REFLASYON": 0.16, "STAGFLASYON": 0.14, "DEFLASYON": 0.18}, True),
            ("Piyasa Faiz İndirim Makası (DGS2 - EFFR)", fed_easing_spread, {"GOLDILOCKS": 0.14, "REFLASYON": 0.14, "STAGFLASYON": 0.10, "DEFLASYON": 0.16}, True),
            ("Ticari Banka Rezervleri (WRESBAL)", wresbal, {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.08, "DEFLASYON": 0.10}, False),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", hy_oas, {"GOLDILOCKS": 0.06, "REFLASYON": 0.08, "STAGFLASYON": 0.16, "DEFLASYON": 0.14}, True),
            # DİP: Sektörel Oranlar ve Volatilite
            ("Yarı İletken Liderliği (SOXX/QQQ)", soxx_qqq_ratio, {"GOLDILOCKS": 0.03, "REFLASYON": 0.04, "STAGFLASYON": 0.04, "DEFLASYON": 0.02}, False),
            ("Yen Carry Trade Döngüsü (USD/JPY)", fetch_yf_data('JPY=X'), {"GOLDILOCKS": 0.02, "REFLASYON": 0.03, "STAGFLASYON": 0.04, "DEFLASYON": 0.02}, False),
            ("VIX Düşük Oynaklık Güveni", vix, {"GOLDILOCKS": 0.01, "REFLASYON": 0.01, "STAGFLASYON": 0.05, "DEFLASYON": 0.04}, True),
            ("NQ / 10Y Risk Primi (QQQ/^TNX)", qqq_tnx_ratio, {"GOLDILOCKS": 0.01, "REFLASYON": 0.01, "STAGFLASYON": 0.03, "DEFLASYON": 0.01}, False),
            ("Öncü Haftalık İstihdam (ICSA)", icsa, {"GOLDILOCKS": 0.005, "REFLASYON": 0.005, "STAGFLASYON": 0.02, "DEFLASYON": 0.02}, True),
            ("MOVE Endeksi (Tahvil Baskısı)", move, {"GOLDILOCKS": 0.005, "REFLASYON": 0.005, "STAGFLASYON": 0.02, "DEFLASYON": 0.01}, True),
        ]
    elif asset == "S&P 500 (SPX)":
        rsp_spy_ratio = safe_ratio(fetch_yf_data('RSP'), fetch_yf_data('SPY'))
        metrics_spec = [
            # ZİRVE: Saf Kredi Koşulları & Likidite Plumbing (%75+)
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", g4_liq, {"GOLDILOCKS": 0.24, "REFLASYON": 0.22, "STAGFLASYON": 0.16, "DEFLASYON": 0.22}, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", nfci, {"GOLDILOCKS": 0.22, "REFLASYON": 0.20, "STAGFLASYON": 0.16, "DEFLASYON": 0.18}, True),
            ("Yüksek Getirili Kredi Güveni (HY OAS)", hy_oas, {"GOLDILOCKS": 0.18, "REFLASYON": 0.18, "STAGFLASYON": 0.14, "DEFLASYON": 0.18}, True),
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", tips_real, {"GOLDILOCKS": 0.14, "REFLASYON": 0.14, "STAGFLASYON": 0.12, "DEFLASYON": 0.16}, True),
            ("Piyasa Faiz İndirim Makası (DGS2 - EFFR)", fed_easing_spread, {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.08, "DEFLASYON": 0.12}, True),
            ("Ticari Banka Rezervleri (WRESBAL)", wresbal, {"GOLDILOCKS": 0.06, "REFLASYON": 0.08, "STAGFLASYON": 0.08, "DEFLASYON": 0.08}, False),
            # DİP: Sektörel Oranlar ve Volatilite
            ("Eşit Ağırlık Piyasa Genişliği (RSP/SPY)", rsp_spy_ratio, {"GOLDILOCKS": 0.02, "REFLASYON": 0.03, "STAGFLASYON": 0.04, "DEFLASYON": 0.02}, False),
            ("Küresel Taşımacılık / Lojistik (IYT)", fetch_yf_data('IYT'), {"GOLDILOCKS": 0.015, "REFLASYON": 0.02, "STAGFLASYON": 0.04, "DEFLASYON": 0.01}, False),
            ("VIX Düşük Oynaklık Güveni", vix, {"GOLDILOCKS": 0.01, "REFLASYON": 0.01, "STAGFLASYON": 0.05, "DEFLASYON": 0.04}, True),
            ("10Y Breakeven Enflasyon İvmesi", t10yie, {"GOLDILOCKS": 0.005, "REFLASYON": 0.01, "STAGFLASYON": 0.04, "DEFLASYON": 0.02}, False),
            ("Öncü Haftalık İstihdam Stresi (ICSA)", icsa, {"GOLDILOCKS": 0.005, "REFLASYON": 0.005, "STAGFLASYON": 0.02, "DEFLASYON": 0.02}, True),
            ("MOVE Endeksi (Tahvil Volatilitesi)", move, {"GOLDILOCKS": 0.005, "REFLASYON": 0.005, "STAGFLASYON": 0.01, "DEFLASYON": 0.01}, True),
        ]
    elif asset == "Kripto (BTC)":
        eth_btc_ratio = safe_ratio(fetch_yf_data('ETH-USD'), fetch_yf_data('BTC-USD'))
        metrics_spec = [
            # ZİRVE: Stablecoin M2 & G4 Likiditesi (%75+)
            ("Stablecoin Küresel Arz İvmesi (DefiLlama)", fetch_defillama_stablecoins(), {"GOLDILOCKS": 0.30, "REFLASYON": 0.28, "STAGFLASYON": 0.24, "DEFLASYON": 0.26}, False),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", g4_liq, {"GOLDILOCKS": 0.26, "REFLASYON": 0.24, "STAGFLASYON": 0.18, "DEFLASYON": 0.24}, False),
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", tips_real, {"GOLDILOCKS": 0.14, "REFLASYON": 0.14, "STAGFLASYON": 0.12, "DEFLASYON": 0.16}, True),
            ("Piyasa Faiz İndirim Makası (DGS2 - EFFR)", fed_easing_spread, {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.08, "DEFLASYON": 0.14}, True),
            ("Chicago Fed Finansal Koşullar (NFCI)", nfci, {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.14, "DEFLASYON": 0.10}, True),
            ("Ticari Banka Rezervleri (WRESBAL)", wresbal, {"GOLDILOCKS": 0.05, "REFLASYON": 0.06, "STAGFLASYON": 0.06, "DEFLASYON": 0.06}, False),
            # DİP: Tali Sentiment ve Oranlar
            ("Kripto Korku & Açgözlülük (F&G)", fetch_crypto_fear_greed(), {"GOLDILOCKS": 0.02, "REFLASYON": 0.03, "STAGFLASYON": 0.06, "DEFLASYON": 0.02}, False),
            ("Kripto-İçi Risk İştahı (ETH/BTC)", eth_btc_ratio, {"GOLDILOCKS": 0.015, "REFLASYON": 0.02, "STAGFLASYON": 0.04, "DEFLASYON": 0.01}, False),
            ("Dolar Endeksi Zayıflığı (DXY)", dxy, {"GOLDILOCKS": 0.01, "REFLASYON": 0.015, "STAGFLASYON": 0.04, "DEFLASYON": 0.04}, True),
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", g4_liq.diff(5), {"GOLDILOCKS": 0.005, "REFLASYON": 0.01, "STAGFLASYON": 0.02, "DEFLASYON": 0.01}, False),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", dgs30, {"GOLDILOCKS": 0.005, "REFLASYON": 0.003, "STAGFLASYON": 0.01, "DEFLASYON": 0.01}, True),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", hy_oas, {"GOLDILOCKS": 0.005, "REFLASYON": 0.002, "STAGFLASYON": 0.01, "DEFLASYON": 0.01}, True),
        ]
    elif asset == "Ham Petrol (WTI)":
        gasoline_bbl = fetch_yf_data('RB=F') * 42.0
        heating_oil_bbl = fetch_yf_data('HO=F') * 42.0
        crude_bbl = fetch_yf_data('CL=F')
        brent_bbl = fetch_yf_data('BZ=F')
        dbc_commodities = fetch_yf_data('DBC')
        natgas = fetch_yf_data('NG=F')
        
        ref_products = (2.0 * gasoline_bbl + 1.0 * heating_oil_bbl) / 3.0
        crack_spread = safe_spread(ref_products, crude_bbl)
        brent_wti_spread = safe_spread(brent_bbl, crude_bbl)
        oil_commodity_ratio = safe_ratio(crude_bbl, dbc_commodities)
        hg_gc_ratio = safe_ratio(fetch_yf_data('HG=F'), fetch_yf_data('GC=F'))

        metrics_spec = [
            # ZİRVE: Fiziki Rafineri Talebi & Deniz Taşımacılığı (%75+)
            ("Küresel Deniz Ticareti/Navlun (BDRY)", bdry, {"GOLDILOCKS": 0.26, "REFLASYON": 0.28, "STAGFLASYON": 0.22, "DEFLASYON": 0.12}, False),
            ("10Y Breakeven Enflasyon İvmesi", t10yie, {"GOLDILOCKS": 0.22, "REFLASYON": 0.24, "STAGFLASYON": 0.26, "DEFLASYON": 0.10}, False),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", g4_liq, {"GOLDILOCKS": 0.18, "REFLASYON": 0.18, "STAGFLASYON": 0.14, "DEFLASYON": 0.18}, False),
            ("Rafineri Çatlak Marjı (Fiziki Talep)", crack_spread, {"GOLDILOCKS": 0.14, "REFLASYON": 0.14, "STAGFLASYON": 0.16, "DEFLASYON": 0.10}, False),
            ("Küresel Fiziki Arz Açığı (Brent/WTI)", brent_wti_spread, {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.12, "DEFLASYON": 0.08}, False),
            # DİP: Tali Enerji & Rasyolar
            ("Enerji / Emtia Rotasyon Gücü (CL/DBC)", oil_commodity_ratio, {"GOLDILOCKS": 0.04, "REFLASYON": 0.03, "STAGFLASYON": 0.04, "DEFLASYON": 0.04}, False),
            ("Doğal Gaz Enerji İvmesi (NG)", natgas, {"GOLDILOCKS": 0.02, "REFLASYON": 0.01, "STAGFLASYON": 0.02, "DEFLASYON": 0.02}, False),
            ("5y5y Forward Enflasyon Çıpası", t5yifr, {"GOLDILOCKS": 0.015, "REFLASYON": 0.008, "STAGFLASYON": 0.02, "DEFLASYON": 0.01}, False),
            ("Bakır / Altın Büyüme Rasyosu (HG/GC)", hg_gc_ratio, {"GOLDILOCKS": 0.01, "REFLASYON": 0.005, "STAGFLASYON": 0.01, "DEFLASYON": 0.01}, False),
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), {"GOLDILOCKS": 0.005, "REFLASYON": 0.003, "STAGFLASYON": 0.005, "DEFLASYON": 0.01}, False),
            ("Dolar Endeksi Zayıflığı (DXY)", dxy, {"GOLDILOCKS": 0.005, "REFLASYON": 0.002, "STAGFLASYON": 0.003, "DEFLASYON": 0.02}, True),
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", tips_real, {"GOLDILOCKS": 0.005, "REFLASYON": 0.002, "STAGFLASYON": 0.002, "DEFLASYON": 0.02}, True),
        ]
    elif asset == "Bakır (HG)":
        hg_cl_ratio = safe_ratio(fetch_yf_data('HG=F'), fetch_yf_data('CL=F'))
        hg_gc_ratio = safe_ratio(fetch_yf_data('HG=F'), fetch_yf_data('GC=F'))
        metrics_spec = [
            # ZİRVE: Kuru Yük Navlun & G4 Likidite (%75+)
            ("Küresel Deniz Ticareti/Navlun (BDRY)", bdry, {"GOLDILOCKS": 0.28, "REFLASYON": 0.28, "STAGFLASYON": 0.20, "DEFLASYON": 0.12}, False),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", g4_liq, {"GOLDILOCKS": 0.24, "REFLASYON": 0.22, "STAGFLASYON": 0.16, "DEFLASYON": 0.22}, False),
            ("10Y Breakeven Enflasyon İvmesi", t10yie, {"GOLDILOCKS": 0.18, "REFLASYON": 0.20, "STAGFLASYON": 0.24, "DEFLASYON": 0.10}, False),
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", tips_real, {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.10, "DEFLASYON": 0.16}, True),
            ("Chicago Fed Finansal Koşullar (NFCI)", nfci, {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.14, "DEFLASYON": 0.12}, True),
            # DİP: Tali Sektörel Rasyolar
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), {"GOLDILOCKS": 0.03, "REFLASYON": 0.03, "STAGFLASYON": 0.05, "DEFLASYON": 0.04}, False),
            ("Bakır / Altın Büyüme Rasyosu (HG/GC)", hg_gc_ratio, {"GOLDILOCKS": 0.02, "REFLASYON": 0.02, "STAGFLASYON": 0.04, "DEFLASYON": 0.04}, False),
            ("Bakır / Petrol Sanayi Rasyosu (HG/CL)", hg_cl_ratio, {"GOLDILOCKS": 0.015, "REFLASYON": 0.015, "STAGFLASYON": 0.03, "DEFLASYON": 0.03}, False),
            ("Küresel Taşımacılık İvmesi (IYT)", fetch_yf_data('IYT'), {"GOLDILOCKS": 0.008, "REFLASYON": 0.008, "STAGFLASYON": 0.02, "DEFLASYON": 0.02}, False),
            ("Piyasa Faiz İndirim Makası (DGS2 - EFFR)", fed_easing_spread, {"GOLDILOCKS": 0.003, "REFLASYON": 0.003, "STAGFLASYON": 0.01, "DEFLASYON": 0.01}, True),
            ("Çin Piyasası İvmesi (MCHI)", fetch_yf_data('MCHI'), {"GOLDILOCKS": 0.002, "REFLASYON": 0.002, "STAGFLASYON": 0.005, "DEFLASYON": 0.005}, False),
            ("Dolar Endeksi Zayıflığı (DXY)", dxy, {"GOLDILOCKS": 0.002, "REFLASYON": 0.002, "STAGFLASYON": 0.005, "DEFLASYON": 0.005}, True),
        ]
    else:
        # ABD TAHVİLİ (TLT)
        metrics_spec = [
            # ZİRVE: Faiz İndirim Döngüsü & Eğri Dikleşmesi (%75+)
            ("Piyasa Faiz İndirim Makası (DGS2 - EFFR)", fed_easing_spread, {"GOLDILOCKS": 0.36, "REFLASYON": 0.34, "STAGFLASYON": 0.28, "DEFLASYON": 0.38}, True),
            ("Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)", t10y2y, {"GOLDILOCKS": 0.30, "REFLASYON": 0.28, "STAGFLASYON": 0.24, "DEFLASYON": 0.30}, False),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", g4_liq, {"GOLDILOCKS": 0.16, "REFLASYON": 0.16, "STAGFLASYON": 0.12, "DEFLASYON": 0.16}, False),
            ("Reel Faiz İndirgeme İvmesi (10Y TIPS)", tips_real, {"GOLDILOCKS": 0.10, "REFLASYON": 0.12, "STAGFLASYON": 0.16, "DEFLASYON": 0.08}, True),
            # DİP: Tali İstihdam ve Enflasyon
            ("Öncü İstihdam Soğuması (ICSA)", icsa, {"GOLDILOCKS": 0.04, "REFLASYON": 0.05, "STAGFLASYON": 0.12, "DEFLASYON": 0.05}, False),
            ("10Y Breakeven Enflasyon İvmesi", t10yie, {"GOLDILOCKS": 0.02, "REFLASYON": 0.03, "STAGFLASYON": 0.05, "DEFLASYON": 0.01}, True),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", dgs30, {"GOLDILOCKS": 0.01, "REFLASYON": 0.01, "STAGFLASYON": 0.02, "DEFLASYON": 0.01}, True),
            ("Küresel Deniz Ticareti/Navlun (BDRY)", bdry, {"GOLDILOCKS": 0.005, "REFLASYON": 0.005, "STAGFLASYON": 0.005, "DEFLASYON": 0.005}, True),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", hy_oas, {"GOLDILOCKS": 0.003, "REFLASYON": 0.003, "STAGFLASYON": 0.003, "DEFLASYON": 0.003}, False),
            ("MOVE Endeksi (Tahvil Volatilitesi)", move, {"GOLDILOCKS": 0.001, "REFLASYON": 0.001, "STAGFLASYON": 0.001, "DEFLASYON": 0.001}, True),
            ("Dolar Endeksi Zayıflığı (DXY)", dxy, {"GOLDILOCKS": 0.001, "REFLASYON": 0.001, "STAGFLASYON": 0.001, "DEFLASYON": 0.001}, False),
        ]

    # --- REJİME GÖRE NORMALİZE EDİLMİŞ DİNAMİK AĞIRLIK HESAPLAMA ---
    target_regime = regime_code if regime_code in ["GOLDILOCKS", "REFLASYON", "STAGFLASYON", "DEFLASYON"] else "GOLDILOCKS"
    
    raw_weights = [item[2].get(target_regime, 0.10) for item in metrics_spec]
    total_w = sum(raw_weights)
    dyn_weights = [w / total_w for w in raw_weights]

    for idx, item in enumerate(metrics_spec):
        name, data_series, weights_dict, invert = item
        dyn_weight = dyn_weights[idx]
        
        z, val = process_indicator(data_series, invert)
        contribution = z * dyn_weight * regime_multiplier
        total_score += contribution
        
        if val == 0:
            display_str = "Hesaplanıyor / Veri Yok"
        elif abs(val) < 0.05: 
            display_str = f"{val:.4f}"
        elif abs(val) < 1000:
            display_str = f"{val:.2f}"
        else:
            display_str = f"{val:,.0f}"
            
        indicators_data.append({
            "Makro Gösterge (Katman)": name,
            "Güncel Değer": display_str,
            "Öncü İvme (Z-Skor)": round(z, 2),
            "Rejim Ağırlığı": f"%{dyn_weight * 100:.1f}",
            "Modele Net Katkı": round(contribution, 3)
        })

# DOĞRUSAL DÖNÜŞÜM & KALİBRE EDİLMİŞ SKOR
raw_portfolio_score = total_score
final_trend_score = float(np.clip(raw_portfolio_score * 45.0, -100.0, 100.0))

if circuit_triggered and final_trend_score > 0:
    final_trend_score = final_trend_score * 0.35 

# --- 7. VOLATİLİTE HEDEFLEME & POZİSYON BOYUTLANDIRMA ---
ticker_asset_map = {
    "Altın (XAU)": "GC=F",
    "Gümüş (XAG)": "SI=F",
    "Nasdaq 100 (NQ)": "QQQ",
    "S&P 500 (SPX)": "SPY",
    "Kripto (BTC)": "BTC-USD",
    "Ham Petrol (WTI)": "CL=F",
    "Bakır (HG)": "HG=F",
    "ABD Tahvili / Faiz (TLT)": "TLT"
}
asset_prices = fetch_yf_data(ticker_asset_map[asset])
if len(asset_prices) > 25:
    realized_vol_20 = float(asset_prices.pct_change().dropna().tail(20).std() * np.sqrt(252) * 100)
else:
    realized_vol_20 = 15.0

vol_scalar = target_vol_input / max(realized_vol_20, 5.0)
raw_position_size = (final_trend_score / 100.0) * vol_scalar * 100.0

if circuit_triggered and raw_position_size > 0:
    raw_position_size = raw_position_size * 0.25 

allocated_position = max(-100.0, min(100.0, raw_position_size))
cash_allocation = 100.0 - abs(allocated_position)

# --- 8. GRAFİKLER VE DASHBOARD ---
col1, col2 = st.columns([1, 1.2])

with col1:
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = final_trend_score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"{asset}<br>Saf Makro Skoru", 'font': {'size': 20}},
        gauge = {
            'axis': {'range': [-100, 100], 'tickwidth': 1},
            'bar': {'color': "black"},
            'steps': [
                {'range': [-100, -60], 'color': "#ff4b4b"},
                {'range': [-60, -20], 'color': "#ffa07a"},
                {'range': [-20, 20], 'color': "#f0e68c"}, 
                {'range': [20, 60], 'color': "#90ee90"}, 
                {'range': [60, 100], 'color': "#32cd32"} 
            ],
        }
    ))
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("#### 💼 Risk Bütçesi ve Pozisyon Dağılımı")
    c_sub1, c_sub2 = st.columns(2)
    with c_sub1:
        st.metric(f"Önerilen {asset} Pozisyonu", f"%{allocated_position:+.1f}", f"Vol Çarpanı: {vol_scalar:.2f}x")
    with c_sub2:
        st.metric("Nakit / Likit Rezerv Payı", f"%{cash_allocation:.1f}", f"Gerçekleşen Vol: %{realized_vol_20:.1f}")

with col2:
    st.markdown("### 📊 Saf Makro Hiyerarşi Tablosu")
    df_results = pd.DataFrame(indicators_data)
    st.dataframe(df_results, use_container_width=True)
    
    st.markdown("""
    **Kurumsal Upstream Hiyerarşi Rehberi:**
    * **Zirvede Saf Makro (%75+ Ağırlık):** Tablonun ilk 5-6 satırı sadece G4 Likidite, Breakeven Enflasyon, TIPS Reel Faiz, Easing Spread ve NFCI Kredi Koşullarından oluşur.
    * **Dipte Tali Oranlar (%2-%4 Ağırlık):** Piyasa içi fiyat oranları (`SOXX`, `RSP`, `DBB`, `VIX`) en alta atılmış, modeli saptırmaları engellenmiştir.
    * **Altın & Gümüş %95 Eşitlik:** Her iki maden de aynı parasal omurgaya bağlanmış, yapay uçurumlar sıfırlanmıştır.
    """)
