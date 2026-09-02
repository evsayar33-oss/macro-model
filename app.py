import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from fredapi import Fred
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. SAYFA VE API AYARLARI ---
st.set_page_config(page_title="Makro Trend v15.0 (Master Unified Grade)", layout="wide")

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
        data.index = pd.to_datetime(data.index)
        return data.resample('B').ffill().dropna()
    except:
        return pd.Series(dtype=float)

@st.cache_data(ttl=1800)
def fetch_yf_data(ticker, days=2500):
    try:
        data = yf.download(ticker, period=f"{days}d", progress=False)
        if 'Close' in data.columns:
            close_data = data['Close']
        else:
            close_data = data.iloc[:, 0]
            
        if isinstance(close_data, pd.DataFrame):
            close_data = close_data.iloc[:, 0]
            
        close_data.index = pd.to_datetime(close_data.index)
        if close_data.index.tz is not None:
            close_data.index = close_data.index.tz_localize(None)
            
        return close_data.resample('B').ffill().dropna()
    except:
        return pd.Series(dtype=float)

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
                return df['mcap'].resample('B').ffill().dropna()
    except:
        pass
    return pd.Series(dtype=float)

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
                return df['val'].resample('B').ffill().dropna()
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
        
        df = pd.DataFrame({
            'w': walcl, 
            't': tga, 
            'r': rrp * 1000,
            'ecb': ecb,
            'eur': eurusd,
            'jpy': usdjpy
        }).dropna()
        
        us_net = df['w'] - df['t'] - df['r']
        ecb_usd = df['ecb'] * df['eur']
        boj_impulse = (df['jpy'] / df['jpy'].rolling(252).mean()) * 2000000.0
        
        g4_total = us_net + (ecb_usd * 0.35) + (boj_impulse * 0.25)
        return g4_total.resample('B').ffill().dropna()
    except:
        walcl = fetch_fred_data('WALCL', days)
        tga = fetch_fred_data('WTREGEN', days)
        rrp = fetch_fred_data('RRPONTSYD', days)
        df = pd.DataFrame({'w': walcl, 't': tga, 'r': rrp * 1000}).dropna()
        return (df['w'] - df['t'] - df['r']).resample('B').ffill().dropna()

# --- 3. REJİM MOTORU ---
def get_realtime_macro_regime():
    t10yie = fetch_fred_data('T10YIE') 
    real_rate = fetch_fred_data('DFII10') 
    icsa = fetch_fred_data('ICSA') 
    consumer_exp = fetch_fred_data('UMCSENT') 
    
    bdry = fetch_yf_data('BDRY') 
    dbc = fetch_yf_data('DBC')   
    
    if len(t10yie) < 60 or len(real_rate) < 60:
        return "NOTR", "NÖTR PİYASA", 1.0, 2.30
        
    lookback_inf = min(len(t10yie), 504)
    inf_dynamic_anchor = float(t10yie.tail(lookback_inf).mean() + (0.20 * t10yie.tail(lookback_inf).std()))
    
    freight_push = bdry.iloc[-1] > bdry.tail(60).mean() if len(bdry) > 60 else False
    commodity_push = dbc.iloc[-1] > dbc.tail(60).mean() if len(dbc) > 60 else False
    
    real_rate_falling = real_rate.iloc[-1] < real_rate.tail(40).mean()
    inf_elevated = (t10yie.iloc[-1] > inf_dynamic_anchor) or (freight_push and commodity_push)
    
    lookback_icsa = min(len(icsa), 130)
    labor_deteriorating = icsa.iloc[-1] > float(icsa.tail(lookback_icsa).quantile(0.65))
    growth_strong = consumer_exp.iloc[-1] > consumer_exp.iloc[-60] if len(consumer_exp) > 60 else True

    if not inf_elevated and real_rate_falling and not labor_deteriorating:
        mult = 1.3 if growth_strong else 1.2
        return "GOLDILOCKS", "GOLDILOCKS (Düşen Reel Maliyetler, Canlı Büyüme)", mult, inf_dynamic_anchor
    elif inf_elevated and not labor_deteriorating:
        mult = 1.2 if growth_strong else 1.1
        return "REFLASYON", "REFLASYON (Genişleyen G4 Likidite & Navlun, Güçlü Büyüme)", mult, inf_dynamic_anchor
    elif inf_elevated and labor_deteriorating:
        mult = 1.4 if not growth_strong else 1.5 
        return "STAGFLASYON", "STAGFLASYON (Yüksek Girdi Maliyetleri, Zayıflayan İstihdam)", mult, inf_dynamic_anchor
    else:
        mult = 1.4
        return "DEFLASYON", "DEFLASYONİST DARALMA (Çöken Emtia/Navlun, Yüksek Reel Sıkılık)", mult, inf_dynamic_anchor

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
        hy_dyn_thresh = max(4.2, float(hy_oas.tail(504).quantile(0.96)))
        oas_z = (hy_oas.iloc[-1] - hy_oas.iloc[-60:].mean()) / (hy_oas.iloc[-60:].std() + 1e-5)
        if oas_z > 2.3 or hy_oas.iloc[-1] > hy_dyn_thresh:
            is_triggered = True
            reasons.append(f"Yüksek Getirili Kredi (HY Spread) Dinamik Stres Eşiğinde ({hy_oas.iloc[-1]:.2f}%)")
            
    if not nfci.empty and len(nfci) > 50:
        nfci_dyn_thresh = max(0.05, float(nfci.tail(252).quantile(0.92)))
        if nfci.iloc[-1] > nfci_dyn_thresh:
            is_triggered = True
            reasons.append(f"Chicago Fed NFCI Sıkılaşma Eşiğinde ({nfci.iloc[-1]:.2f} > {nfci_dyn_thresh:.2f})")
        
    if not vix.empty and len(vix) > 60:
        vix_dyn_thresh = max(26.0, float(vix.tail(504).quantile(0.96)))
        if vix.iloc[-1] > vix_dyn_thresh:
            is_triggered = True
            reasons.append(f"VIX Panik Eşiğinde ({vix.iloc[-1]:.1f} > {vix_dyn_thresh:.1f})")
        
    return is_triggered, reasons

# --- 5. BİRLEŞİK EKONOMETRİK Z-SKOR MOTORU (KUSURSUZ İVME STANDARDI) ---
def process_indicator(data_series, invert=False):
    if isinstance(data_series, pd.DataFrame):
        data_series = data_series.iloc[:, 0]
        
    data_series = data_series.dropna()
    
    if len(data_series) < 60:
        val = float(data_series.iloc[-1]) if not data_series.empty else 0.0
        return 0.0, val
    
    current_val = float(data_series.iloc[-1])
    
    # Tüm göstergeler için evrensel standart: 40G Trend vs 252G Döngü Ortalaması
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
st.title("🏛️ KÜRESEL MAKRO MODELİ (v15.0 - MASTER UNIFIED)")
st.markdown("**Harmonize Edilmiş Değerli Metaller, Tahvil İvmesi ve G4 Küresel Makro Motoru**")

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
    st.metric("Aktif Piyasa Rejimi (G4 / Navlun Bazlı)", regime_code, f"Çarpan: {regime_multiplier}x")
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

with st.spinner(f"{asset} için Harmonize Faktörler Hesaplanıyor..."):
    # Format: (Gösterge Adı, Data, Ağırlık Sözlüğü {GOLDILOCKS, REFLASYON, STAGFLASYON, DEFLASYON}, TersMi)
    
    if asset == "Altın (XAU)":
        # Altın & Gümüş ortak parasal omurga (%75 ortak)
        metrics_spec = [
            ("Reel Faiz İndirgeme İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.22, "REFLASYON": 0.20, "STAGFLASYON": 0.18, "DEFLASYON": 0.22}, True),
            ("10Y Breakeven Enflasyon Genişlemesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.20, "STAGFLASYON": 0.24, "DEFLASYON": 0.08}, False), 
            ("Piyasa Faiz İndirim Döngüsü (2Y Yield)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.12, "DEFLASYON": 0.20}, True),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.14, "DEFLASYON": 0.18}, False), 
            ("Dolar Endeksi Zayıflığı (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.14, "REFLASYON": 0.12, "STAGFLASYON": 0.08, "DEFLASYON": 0.14}, True),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.08, "DEFLASYON": 0.08}, True),
            ("Küresel Tedarik/Navlun Baskısı (BDRY)", fetch_yf_data('BDRY'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.16, "DEFLASYON": 0.10}, False),
        ]
    elif asset == "Gümüş (XAG)":
        # Altın ile tam uyumlu parasal omurga + dengeli sanayi faktörü
        metrics_spec = [
            ("Reel Faiz İndirgeme İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.20, "REFLASYON": 0.18, "STAGFLASYON": 0.16, "DEFLASYON": 0.20}, True),
            ("10Y Breakeven Enflasyon Genişlemesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.18, "STAGFLASYON": 0.22, "DEFLASYON": 0.08}, False), 
            ("Piyasa Faiz İndirim Döngüsü (2Y Yield)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.16, "REFLASYON": 0.14, "STAGFLASYON": 0.10, "DEFLASYON": 0.18}, True),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.16, "REFLASYON": 0.14, "STAGFLASYON": 0.12, "DEFLASYON": 0.16}, False), 
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), {"GOLDILOCKS": 0.14, "REFLASYON": 0.14, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False),
            ("Dolar Endeksi Zayıflığı (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.08, "DEFLASYON": 0.12}, True),
            ("Küresel Tedarik/Navlun Baskısı (BDRY)", fetch_yf_data('BDRY'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.14, "DEFLASYON": 0.10}, False),
        ]
    elif asset == "Nasdaq 100 (NQ)":
        metrics_spec = [
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.22, "REFLASYON": 0.20, "STAGFLASYON": 0.18, "DEFLASYON": 0.24}, True),
            ("Piyasa Faiz İndirim Döngüsü (2Y Yield)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.14, "DEFLASYON": 0.20}, True),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.20, "REFLASYON": 0.18, "STAGFLASYON": 0.12, "DEFLASYON": 0.18}, False), 
            ("Yarı İletken Liderliği (SOXX/QQQ)", fetch_yf_data('SOXX') / fetch_yf_data('QQQ'), {"GOLDILOCKS": 0.16, "REFLASYON": 0.14, "STAGFLASYON": 0.06, "DEFLASYON": 0.06}, False),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.14, "DEFLASYON": 0.10}, True),
            ("Öncü İstihdam Soğuması (ICSA)", fetch_fred_data('ICSA'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.10, "STAGFLASYON": 0.16, "DEFLASYON": 0.12}, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), {"GOLDILOCKS": 0.06, "REFLASYON": 0.12, "STAGFLASYON": 0.20, "DEFLASYON": 0.10}, True),
        ]
    elif asset == "S&P 500 (SPX)":
        metrics_spec = [
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.22, "REFLASYON": 0.20, "STAGFLASYON": 0.16, "DEFLASYON": 0.24}, True),
            ("Piyasa Faiz İndirim Döngüsü (2Y Yield)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.12, "DEFLASYON": 0.18}, True),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.12, "DEFLASYON": 0.18}, False), 
            ("Eşit Ağırlık Piyasa Genişliği (RSP/SPY)", fetch_yf_data('RSP') / fetch_yf_data('SPY'), {"GOLDILOCKS": 0.16, "REFLASYON": 0.15, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False),
            ("Öncü İstihdam Soğuması (ICSA)", fetch_fred_data('ICSA'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.11, "STAGFLASYON": 0.16, "DEFLASYON": 0.16}, False),
            ("Küresel Taşımacılık / Lojistik (IYT)", fetch_yf_data('IYT'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.11, "STAGFLASYON": 0.16, "DEFLASYON": 0.08}, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), {"GOLDILOCKS": 0.06, "REFLASYON": 0.12, "STAGFLASYON": 0.20, "DEFLASYON": 0.10}, True),
        ]
    elif asset == "Kripto (BTC)":
        metrics_spec = [
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.24, "REFLASYON": 0.22, "STAGFLASYON": 0.14, "DEFLASYON": 0.22}, False),
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.20, "REFLASYON": 0.18, "STAGFLASYON": 0.14, "DEFLASYON": 0.20}, True),
            ("Piyasa Faiz İndirim Döngüsü (2Y Yield)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.12, "DEFLASYON": 0.18}, True),
            ("Stablecoin Küresel Arz İvmesi (DefiLlama)", fetch_defillama_stablecoins(), {"GOLDILOCKS": 0.16, "REFLASYON": 0.16, "STAGFLASYON": 0.14, "DEFLASYON": 0.16}, False),
            ("Kripto-İçi Risk İştahı (ETH/BTC)", fetch_yf_data('ETH-USD') / fetch_yf_data('BTC-USD'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.14, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False),
            ("Kripto Korku & Açgözlülük (F&G)", fetch_crypto_fear_greed(), {"GOLDILOCKS": 0.06, "REFLASYON": 0.08, "STAGFLASYON": 0.26, "DEFLASYON": 0.08}, False),
            ("Dolar Endeksi Zayıflığı (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.04, "REFLASYON": 0.06, "STAGFLASYON": 0.12, "DEFLASYON": 0.10}, True),
        ]
    elif asset == "Ham Petrol (WTI)":
        gasoline_bbl = fetch_yf_data('RB=F') * 42.0
        heating_oil_bbl = fetch_yf_data('HO=F') * 42.0
        crude_bbl = fetch_yf_data('CL=F')
        brent_bbl = fetch_yf_data('BZ=F')
        dbc_commodities = fetch_yf_data('DBC')
        natgas = fetch_yf_data('NG=F')
        
        crack_spread = ((2 * gasoline_bbl + 1 * heating_oil_bbl) / 3) - crude_bbl
        brent_wti_spread = brent_bbl - crude_bbl
        oil_commodity_ratio = crude_bbl / dbc_commodities

        metrics_spec = [
            ("Rafineri Çatlak Marjı (Fiziki Talep)", crack_spread, {"GOLDILOCKS": 0.16, "REFLASYON": 0.22, "STAGFLASYON": 0.20, "DEFLASYON": 0.10}, False),
            ("Küresel Deniz Ticareti/Navlun (BDRY)", fetch_yf_data('BDRY'), {"GOLDILOCKS": 0.14, "REFLASYON": 0.18, "STAGFLASYON": 0.16, "DEFLASYON": 0.08}, False), 
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.18, "STAGFLASYON": 0.20, "DEFLASYON": 0.08}, False),
            ("Küresel Fiziki Arz Açığı (Brent/WTI)", brent_wti_spread, {"GOLDILOCKS": 0.14, "REFLASYON": 0.16, "STAGFLASYON": 0.18, "DEFLASYON": 0.10}, False),
            ("Doğal Gaz Enerji İvmesi (NG)", natgas, {"GOLDILOCKS": 0.10, "REFLASYON": 0.12, "STAGFLASYON": 0.14, "DEFLASYON": 0.06}, False), 
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.10, "DEFLASYON": 0.14}, True),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.12, "REFLASYON": 0.10, "STAGFLASYON": 0.08, "DEFLASYON": 0.10}, False),
            ("Dolar Endeksi Zayıflığı (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.08, "STAGFLASYON": 0.06, "DEFLASYON": 0.12}, True),
        ]
    elif asset == "Bakır (HG)":
        metrics_spec = [
            ("Küresel Deniz Ticareti/Navlun (BDRY)", fetch_yf_data('BDRY'), {"GOLDILOCKS": 0.22, "REFLASYON": 0.22, "STAGFLASYON": 0.12, "DEFLASYON": 0.08}, False), 
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), {"GOLDILOCKS": 0.20, "REFLASYON": 0.18, "STAGFLASYON": 0.10, "DEFLASYON": 0.08}, False),
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.14, "REFLASYON": 0.14, "STAGFLASYON": 0.10, "DEFLASYON": 0.14}, False),
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.12, "DEFLASYON": 0.16}, True),
            ("Piyasa Faiz İndirim Döngüsü (2Y Yield)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.10, "STAGFLASYON": 0.32, "DEFLASYON": 0.32}, True),
            ("Dolar Endeksi Zayıflığı (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.06, "REFLASYON": 0.08, "STAGFLASYON": 0.10, "DEFLASYON": 0.08}, True),
        ]
    else:
        # ABD TAHVİLİ (TLT) - FAİZ İNDİRİMİ VE REEL FAİZ İNİŞİ %100 BOĞA ÇALIŞIR
        metrics_spec = [
            ("Piyasa Faiz İndirim Döngüsü (2Y Yield)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.28, "REFLASYON": 0.26, "STAGFLASYON": 0.24, "DEFLASYON": 0.30}, True), # Faiz indikçe TLT AL
            ("Reel Faiz İndirgeme İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.24, "REFLASYON": 0.22, "STAGFLASYON": 0.20, "DEFLASYON": 0.26}, True), # Reel faiz indikçe TLT AL
            ("Öncü İstihdam Soğuması (ICSA)", fetch_fred_data('ICSA'), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.20, "DEFLASYON": 0.20}, False), # İstihdam soğudukça TLT AL
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.14, "STAGFLASYON": 0.16, "DEFLASYON": 0.08}, True),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.12, "STAGFLASYON": 0.12, "DEFLASYON": 0.08}, True),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.08, "REFLASYON": 0.06, "STAGFLASYON": 0.04, "DEFLASYON": 0.08}, False),
        ]

    # --- REJİME GÖRE NORMALİZE EDİLMİŞ DİNAMİK AĞIRLIK HESAPLAMA ---
    target_regime = regime_code if regime_code in ["GOLDILOCKS", "REFLASYON", "STAGFLASYON", "DEFLASYON"] else "REFLASYON"
    
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
            "Makro İvme (Z-Skor)": round(z, 2),
            "Rejim Ağırlığı": f"%{dyn_weight * 100:.1f}",
            "Modele Net Katkı": round(contribution, 3)
        })

# DENGELİ VE GERÇEKÇİ DOĞRUSAL DÖNÜŞÜM (AŞIRI UÇLAR SIFIRLANDI)
raw_portfolio_score = total_score
final_trend_score = float(np.clip(raw_portfolio_score * 35.0, -100.0, 100.0))

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
        title = {'text': f"{asset}<br>Master Makro Skoru", 'font': {'size': 20}},
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
    st.markdown("### 📊 Master Harmonize Faktör Tablosu")
    df_results = pd.DataFrame(indicators_data)
    st.dataframe(df_results, use_container_width=True)
    
    st.markdown("""
    **Kurumsal Master Rehberi:**
    * **Harmonize Parasal Omurga:** Altın ve Gümüş'ün reel faiz, enflasyon ve G4 likidite duyarlılıkları %75 ortak temele bağlanmıştır.
    * **Tahvil (TLT) İvmesi:** Faizlerin düşüşü doğrudan tahvil için BOĞA (AL) yönlü olarak kalibre edilmiştir.
    * **Universal Z-Skor Standardı:** Tüm göstergeler 40G trend ve 252G döngü tabanına göre matematiksel çelişki olmadan ölçülür.
    """)
