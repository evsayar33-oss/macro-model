import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from fredapi import Fred
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. SAYFA VE API AYARLARI ---
st.set_page_config(page_title="Makro Trend v10.0 (Ultra-Calibrated Fed Grade)", layout="wide")

try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=FRED_API_KEY)
except:
    st.error("Lütfen Streamlit Cloud ayarlarına FRED_API_KEY eklediğinizden emin olun!")
    st.stop()

# --- 2. GELİŞMİŞ MERKEZ BANKASI, FİZİKİ EMTİA & LİKİDİTE MOTORU ---
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
                return df['mcap'].resample('B').ffill().dropna()
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
                return df['val'].resample('B').ffill().dropna()
    except:
        pass
    return pd.Series(dtype=float)

# KÜRESEL NET DOLAR LİKİDİTESİ: (Fed Bilançosu - TGA - RRP) + (ECB Bilançosu in USD)
@st.cache_data(ttl=1800)
def fetch_global_net_liquidity(days=2500):
    try:
        walcl = fetch_fred_data('WALCL', days)       
        tga = fetch_fred_data('WTREGEN', days)       
        rrp = fetch_fred_data('RRPONTSYD', days)     
        ecb = fetch_fred_data('ECBASSETSW', days)   
        eurusd = fetch_yf_data('EURUSD=X', days)     
        
        df = pd.DataFrame({
            'w': walcl, 
            't': tga, 
            'r': rrp * 1000,
            'ecb': ecb,
            'eur': eurusd
        }).dropna()
        
        us_net = df['w'] - df['t'] - df['r']
        ecb_usd = df['ecb'] * df['eur']
        global_net = us_net + (ecb_usd * 0.4) 
        return global_net.resample('B').ffill().dropna()
    except:
        walcl = fetch_fred_data('WALCL', days)
        tga = fetch_fred_data('WTREGEN', days)
        rrp = fetch_fred_data('RRPONTSYD', days)
        df = pd.DataFrame({'w': walcl, 't': tga, 'r': rrp * 1000}).dropna()
        return (df['w'] - df['t'] - df['r']).resample('B').ffill().dropna()

# --- 3. TAM OTONOM KENDİNİ KALİBRE EDEN REJİM MOTORU ---
def get_realtime_macro_regime():
    t10yie = fetch_fred_data('T10YIE') 
    fwd_inf = fetch_fred_data('T5YIFR') 
    icsa = fetch_fred_data('ICSA') 
    consumer_exp = fetch_fred_data('UMCSENT') 
    
    if len(t10yie) < 60 or len(icsa) < 60:
        return "NOTR", "NÖTR PİYASA", 1.0, 2.30
        
    lookback_inf = min(len(t10yie), 504)
    inf_dynamic_anchor = float(t10yie.tail(lookback_inf).mean() + (0.20 * t10yie.tail(lookback_inf).std()))
    
    inf_momentum = t10yie.iloc[-1] > t10yie.iloc[-30]
    inf_elevated = t10yie.iloc[-1] > inf_dynamic_anchor
    fwd_rising = fwd_inf.iloc[-1] > fwd_inf.iloc[-40] if len(fwd_inf) > 40 else False
    
    inflation_pressure = (inf_momentum or inf_elevated) and (fwd_rising or inf_elevated)
    
    lookback_icsa = min(len(icsa), 130)
    labor_deteriorating = icsa.iloc[-1] > float(icsa.tail(lookback_icsa).quantile(0.65))
    growth_strong = consumer_exp.iloc[-1] > consumer_exp.iloc[-60] if len(consumer_exp) > 60 else True

    if not inflation_pressure and not labor_deteriorating:
        mult = 1.3 if growth_strong else 1.2
        return "GOLDILOCKS", "GOLDILOCKS (Düşen Enflasyon Beklentisi, Güçlü Büyüme)", mult, inf_dynamic_anchor
    elif inflation_pressure and not labor_deteriorating:
        mult = 1.2 if growth_strong else 1.1
        return "REFLASYON", "REFLASYON (Genişleyen Enflasyon Beklentisi, Güçlü Büyüme)", mult, inf_dynamic_anchor
    elif inflation_pressure and labor_deteriorating:
        mult = 1.4 if not growth_strong else 1.5 
        return "STAGFLASYON", "STAGFLASYON (Artan Enflasyon Fiyatlaması, Zayıflayan İstihdam)", mult, inf_dynamic_anchor
    else:
        mult = 1.4
        return "DEFLASYON", "DEFLASYONİST DARALMA (Çöken Enflasyon, Resesyon Baskısı)", mult, inf_dynamic_anchor

# --- 4. OTONOM ŞALTER VE KUYRUK RİSKİ MOTORU ---
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

# --- 5. EKONOMETRİK DENGELİ Z-SKOR MOTORU ---
def process_indicator(data_series, invert=False, is_rate=False):
    if isinstance(data_series, pd.DataFrame):
        data_series = data_series.iloc[:, 0]
        
    data_series = data_series.dropna()
    
    if len(data_series) < 100:
        val = float(data_series.iloc[-1]) if not data_series.empty else 0.0
        return 0.0, val
    
    current_val = float(data_series.iloc[-1])
    
    if is_rate:
        # Faizler ve oranlar için: Son 40 günlük değişim ve 1 yıllık seviye konumu
        mean_lvl = data_series.rolling(window=252).mean().iloc[-1]
        std_lvl = data_series.rolling(window=252).std().iloc[-1]
        z_level = (current_val - mean_lvl) / (std_lvl + 1e-5)
        
        diff_40 = data_series.diff(40).dropna()
        std_diff = diff_40.rolling(window=252).std().iloc[-1]
        z_mom = (diff_40.iloc[-1]) / (std_diff + 1e-5) if std_diff > 0 else 0.0
        
        base_z_score = 0.5 * z_level + 0.5 * z_mom
    else:
        # Fiyat ve Rasyolar için: 40G EMA'nın 252G Ortalamaya Uzaklığı
        ema_40 = data_series.ewm(span=40, adjust=False).mean()
        mean_252 = data_series.rolling(window=252).mean().iloc[-1]
        std_252 = data_series.rolling(window=252).std().iloc[-1]
        base_z_score = (ema_40.iloc[-1] - mean_252) / (std_252 + 1e-5)
        
    if invert:
        base_z_score = -base_z_score
        
    z_score = float(max(-2.5, min(2.5, base_z_score)))
    display_val = current_val
    return z_score, display_val

# --- 6. ARAYÜZ VE UYGULAMA ---
st.title("🏛️ KÜRESEL MAKRO MODELİ (v10.0 - ULTRA-CALIBRATED)")
st.markdown("**Varlık Bazlı Tam Dinamik Rejim Matrisi & Kalibre Edilmiş Makro Motoru**")

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
    st.metric("Aktif Piyasa Rejimi (Otonom)", regime_code, f"Çarpan: {regime_multiplier}x")
with col_info2:
    if circuit_triggered:
        st.metric("Sistemik Risk Şalteri", "🚨 AKTİF (KORUMA MODU)", "Risk Azaltıldı", delta_color="inverse")
    else:
        st.metric("Sistemik Risk Şalteri", "✅ NORMAL (OTONOM)", "Dinamik Eşikler Dengeli")
with col_info3:
    t10_val = fetch_fred_data('T10YIE')
    st.metric("10Y Breakeven Enflasyon", f"%{t10_val.iloc[-1]:.2f}" if not t10_val.empty else "N/A", f"Otonom Çıpa: %{dynamic_inf_anchor:.2f}")

if circuit_triggered:
    st.error(f"⚠️ **SİSTEMİK RİSK ŞALTERİ DEVREDE:** Aşağıdaki dinamik persentil kırılımları sebebiyle alım sinyalleri baskılanmıştır:\n* " + "\n* ".join(circuit_reasons))

indicators_data = []
total_score = 0

with st.spinner(f"{asset} için Rejime Özel Dinamik Faktörler Hesaplanıyor..."):
    # Format: (Gösterge Adı, Data, Ağırlık Sözlüğü {GOLDILOCKS, REFLASYON, STAGFLASYON, DEFLASYON}, TersMi, FaizMi)
    
    if asset == "Altın (XAU)":
        metrics_spec = [
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.18, "REFLASYON": 0.12, "STAGFLASYON": 0.08, "DEFLASYON": 0.14}, True, True),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.15, "STAGFLASYON": 0.20, "DEFLASYON": 0.06}, False, True), 
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), {"GOLDILOCKS": 0.14, "REFLASYON": 0.12, "STAGFLASYON": 0.10, "DEFLASYON": 0.15}, False, False), 
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.10, "STAGFLASYON": 0.10, "DEFLASYON": 0.16}, True, True),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.11, "STAGFLASYON": 0.08, "DEFLASYON": 0.12}, True, False),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.09, "STAGFLASYON": 0.08, "DEFLASYON": 0.10}, True, True),
            ("MOVE Endeksi (Tahvil/Jeopolitik Panik)", fetch_yf_data('^MOVE'), {"GOLDILOCKS": 0.06, "REFLASYON": 0.08, "STAGFLASYON": 0.16, "DEFLASYON": 0.10}, False, False),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), {"GOLDILOCKS": 0.06, "REFLASYON": 0.07, "STAGFLASYON": 0.12, "DEFLASYON": 0.10}, False, True),
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.05, "DEFLASYON": 0.05}, False, False),
            ("5y5y Forward Enflasyon Çıpası", fetch_fred_data('T5YIFR'), {"GOLDILOCKS": 0.06, "REFLASYON": 0.08, "STAGFLASYON": 0.13, "DEFLASYON": 0.02}, False, True),
        ]
    elif asset == "Gümüş (XAG)":
        metrics_spec = [
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False, False),
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), {"GOLDILOCKS": 0.15, "REFLASYON": 0.14, "STAGFLASYON": 0.06, "DEFLASYON": 0.05}, False, False),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.14, "STAGFLASYON": 0.18, "DEFLASYON": 0.06}, False, True), 
            ("Küresel Taşımacılık İvmesi (IYT)", fetch_yf_data('IYT'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.06, "DEFLASYON": 0.05}, False, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.09, "STAGFLASYON": 0.10, "DEFLASYON": 0.15}, True, True),
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), {"GOLDILOCKS": 0.12, "REFLASYON": 0.10, "STAGFLASYON": 0.10, "DEFLASYON": 0.14}, False, False), 
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.09, "STAGFLASYON": 0.08, "DEFLASYON": 0.12}, True, False),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.07, "STAGFLASYON": 0.08, "DEFLASYON": 0.10}, True, True),
            ("Altın / Gümüş Değerleme Rasyosu", fetch_yf_data('GC=F') / fetch_yf_data('SI=F'), {"GOLDILOCKS": 0.07, "REFLASYON": 0.09, "STAGFLASYON": 0.08, "DEFLASYON": 0.07}, True, False),
        ]
    elif asset == "Nasdaq 100 (NQ)":
        metrics_spec = [
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), {"GOLDILOCKS": 0.18, "REFLASYON": 0.15, "STAGFLASYON": 0.10, "DEFLASYON": 0.16}, False, False), 
            ("Yarı İletken Liderliği (SOXX/QQQ)", fetch_yf_data('SOXX') / fetch_yf_data('QQQ'), {"GOLDILOCKS": 0.16, "REFLASYON": 0.14, "STAGFLASYON": 0.06, "DEFLASYON": 0.05}, False, False),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.10, "STAGFLASYON": 0.14, "DEFLASYON": 0.10}, True, True),
            ("Öncü Haftalık İstihdam Stresi (ICSA)", fetch_fred_data('ICSA'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.14, "DEFLASYON": 0.15}, True, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.11, "STAGFLASYON": 0.12, "DEFLASYON": 0.14}, True, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.09, "STAGFLASYON": 0.12, "DEFLASYON": 0.14}, True, True),
            ("Ticari Banka Rezervleri (WRESBAL)", fetch_fred_data('WRESBAL'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.08, "DEFLASYON": 0.10}, False, False),
            ("Yen Carry Trade Döngüsü (USD/JPY)", fetch_yf_data('JPY=X'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.06, "DEFLASYON": 0.06}, False, False),
            ("VIX Volatilite Eğilimi", fetch_yf_data('^VIX'), {"GOLDILOCKS": 0.04, "REFLASYON": 0.05, "STAGFLASYON": 0.10, "DEFLASYON": 0.10}, True, False),
        ]
    elif asset == "S&P 500 (SPX)":
        metrics_spec = [
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), {"GOLDILOCKS": 0.16, "REFLASYON": 0.14, "STAGFLASYON": 0.10, "DEFLASYON": 0.15}, False, False), 
            ("Eşit Ağırlık Piyasa Genişliği (RSP/SPY)", fetch_yf_data('RSP') / fetch_yf_data('SPY'), {"GOLDILOCKS": 0.15, "REFLASYON": 0.14, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False, False),
            ("Öncü Haftalık İstihdam Stresi (ICSA)", fetch_fred_data('ICSA'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.11, "STAGFLASYON": 0.15, "DEFLASYON": 0.16}, True, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.11, "STAGFLASYON": 0.13, "DEFLASYON": 0.14}, True, False),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.09, "STAGFLASYON": 0.12, "DEFLASYON": 0.09}, True, True),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.09, "STAGFLASYON": 0.11, "DEFLASYON": 0.14}, True, True),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.09, "STAGFLASYON": 0.13, "DEFLASYON": 0.12}, True, True),
            ("Ticari Banka Rezervleri (WRESBAL)", fetch_fred_data('WRESBAL'), {"GOLDILOCKS": 0.09, "REFLASYON": 0.09, "STAGFLASYON": 0.08, "DEFLASYON": 0.08}, False, False),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.14, "STAGFLASYON": 0.10, "DEFLASYON": 0.06}, False, True), 
        ]
    elif asset == "Kripto (BTC)":
        metrics_spec = [
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.12, "DEFLASYON": 0.16}, False, False),
            ("Stablecoin Küresel Arz İvmesi (DefiLlama)", fetch_defillama_stablecoins(), {"GOLDILOCKS": 0.16, "REFLASYON": 0.15, "STAGFLASYON": 0.12, "DEFLASYON": 0.14}, False, False),
            ("Kripto-İçi Risk İştahı (ETH/BTC)", fetch_yf_data('ETH-USD') / fetch_yf_data('BTC-USD'), {"GOLDILOCKS": 0.14, "REFLASYON": 0.13, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False, False),
            ("Kripto Korku & Açgözlülük (F&G)", fetch_crypto_fear_greed(), {"GOLDILOCKS": 0.12, "REFLASYON": 0.11, "STAGFLASYON": 0.12, "DEFLASYON": 0.12}, False, False),
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.09, "STAGFLASYON": 0.12, "DEFLASYON": 0.12}, True, True),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.09, "STAGFLASYON": 0.12, "DEFLASYON": 0.14}, True, True),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.09, "STAGFLASYON": 0.12, "DEFLASYON": 0.12}, True, False),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.09, "STAGFLASYON": 0.08, "DEFLASYON": 0.10}, True, False),
            ("Ticari Banka Rezervleri (WRESBAL)", fetch_fred_data('WRESBAL'), {"GOLDILOCKS": 0.04, "REFLASYON": 0.09, "STAGFLASYON": 0.12, "DEFLASYON": 0.04}, False, False),
        ]
    elif asset == "Ham Petrol (WTI)":
        gasoline_bbl = fetch_yf_data('RB=F') * 42.0
        heating_oil_bbl = fetch_yf_data('HO=F') * 42.0
        crude_bbl = fetch_yf_data('CL=F')
        brent_bbl = fetch_yf_data('BZ=F')
        dbc_commodities = fetch_yf_data('DBC')
        
        crack_spread = ((2 * gasoline_bbl + 1 * heating_oil_bbl) / 3) - crude_bbl
        brent_wti_spread = brent_bbl - crude_bbl
        oil_commodity_ratio = crude_bbl / dbc_commodities

        metrics_spec = [
            ("Rafineri Çatlak Marjı (Fiziki Talep)", crack_spread, {"GOLDILOCKS": 0.15, "REFLASYON": 0.20, "STAGFLASYON": 0.18, "DEFLASYON": 0.08}, False, False),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.18, "STAGFLASYON": 0.20, "DEFLASYON": 0.06}, False, True),
            ("Küresel Fiziki Arz Açığı (Brent/WTI)", brent_wti_spread, {"GOLDILOCKS": 0.12, "REFLASYON": 0.16, "STAGFLASYON": 0.18, "DEFLASYON": 0.08}, False, False),
            ("Enerji / Emtia Rotasyon Gücü", oil_commodity_ratio, {"GOLDILOCKS": 0.12, "REFLASYON": 0.14, "STAGFLASYON": 0.14, "DEFLASYON": 0.08}, False, False),
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), {"GOLDILOCKS": 0.15, "REFLASYON": 0.12, "STAGFLASYON": 0.05, "DEFLASYON": 0.05}, False, False),
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), {"GOLDILOCKS": 0.14, "REFLASYON": 0.10, "STAGFLASYON": 0.05, "DEFLASYON": 0.05}, False, False),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.08, "DEFLASYON": 0.12}, True, False),
            ("5y5y Forward Enflasyon Çıpası", fetch_fred_data('T5YIFR'), {"GOLDILOCKS": 0.06, "REFLASYON": 0.08, "STAGFLASYON": 0.12, "DEFLASYON": 0.04}, False, True),
        ]
    elif asset == "Bakır (HG)":
        metrics_spec = [
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), {"GOLDILOCKS": 0.20, "REFLASYON": 0.18, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False, False),
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.06, "DEFLASYON": 0.05}, False, False),
            ("Küresel Taşımacılık İvmesi (IYT)", fetch_yf_data('IYT'), {"GOLDILOCKS": 0.15, "REFLASYON": 0.14, "STAGFLASYON": 0.06, "DEFLASYON": 0.05}, False, False),
            ("Bakır / Petrol Sanayi Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('CL=F'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False, False),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.12, "STAGFLASYON": 0.16, "DEFLASYON": 0.06}, False, True),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.09, "REFLASYON": 0.09, "STAGFLASYON": 0.08, "DEFLASYON": 0.12}, True, False),
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.08, "DEFLASYON": 0.12}, False, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.09, "STAGFLASYON": 0.10, "DEFLASYON": 0.14}, True, True),
        ]
    else:
        # ABD TAHVİLİ / FAİZ (TLT)
        metrics_spec = [
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), {"GOLDILOCKS": 0.18, "REFLASYON": 0.14, "STAGFLASYON": 0.15, "DEFLASYON": 0.22}, True, True),
            ("Öncü Haftalık İstihdam Stresi (ICSA)", fetch_fred_data('ICSA'), {"GOLDILOCKS": 0.14, "REFLASYON": 0.12, "STAGFLASYON": 0.18, "DEFLASYON": 0.20}, False, False),
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.16, "REFLASYON": 0.14, "STAGFLASYON": 0.12, "DEFLASYON": 0.18}, True, True),
            ("Getiri Eğrisi Eğim İvmesi (10Y-2Y)", fetch_fred_data('T10Y2Y'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.10, "DEFLASYON": 0.14}, False, True),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.16, "STAGFLASYON": 0.18, "DEFLASYON": 0.06}, True, True),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.12, "STAGFLASYON": 0.12, "DEFLASYON": 0.08}, True, True),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.10, "DEFLASYON": 0.12}, False, True),
            ("MOVE Endeksi (Tahvil Volatilitesi)", fetch_yf_data('^MOVE'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.05, "DEFLASYON": 0.04}, True, False),
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), {"GOLDILOCKS": 0.04, "REFLASYON": 0.04, "STAGFLASYON": 0.00, "DEFLASYON": 0.06}, False, False),
        ]

    # --- REJİME GÖRE OTOMATİK NORMALİZE EDİLMİŞ DİNAMİK AĞIRLIK MOTORU ---
    target_regime = regime_code if regime_code in ["GOLDILOCKS", "REFLASYON", "STAGFLASYON", "DEFLASYON"] else "REFLASYON"
    
    raw_weights = [item[2].get(target_regime, 0.10) for item in metrics_spec]
    total_w = sum(raw_weights)
    dyn_weights = [w / total_w for w in raw_weights]

    for idx, item in enumerate(metrics_spec):
        name, data_series, weights_dict, invert, is_rate = item
        dyn_weight = dyn_weights[idx]
        
        z, val = process_indicator(data_series, invert, is_rate)
        contribution = z * dyn_weight * regime_multiplier
        total_score += contribution
        
        if val == 0:
            display_str = "Hesaplanıyor / Veri Yok"
        elif is_rate:
            display_str = f"%{val:.2f}"
        elif abs(val) < 0.05: 
            display_str = f"{val:.4f}"
        else:
            display_str = f"{val:.2f}" if abs(val) < 1000 else f"{val:,.0f}"
            
        indicators_data.append({
            "Makro Gösterge (Katman)": name,
            "Güncel Değer": display_str,
            "Ekonometrik İvme (Z-Skor)": round(z, 2),
            "Rejim Ağırlığı": f"%{dyn_weight * 100:.1f}",
            "Modele Net Katkı": round(contribution, 3)
        })

# KALİBRE EDİLMİŞ TANH DÖNÜŞÜMÜ (SIKIŞMA VE PATLAMA ORTADAN KALDIRILDI)
final_trend_score = float(np.tanh(total_score / 1.35) * 100.0)
final_trend_score = max(-100.0, min(100.0, final_trend_score))

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
        title = {'text': f"{asset}<br>Ultra-Calibrated Makro Skoru", 'font': {'size': 20}},
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
    st.markdown("### 📊 Ultra-Calibrated Faktör Dağılım Tablosu")
    df_results = pd.DataFrame(indicators_data)
    st.dataframe(df_results, use_container_width=True)
    
    st.markdown("""
    **Kurumsal Ultra-Calibrated Rehberi:**
    * **Varlık Bazlı Rejim Matrisi:** Her varlığın her göstergesi aktif makro rejime (`GOLDILOCKS, REFLASYON, STAGFLASYON, DEFLASYON`) göre dinamik ağırlık alır.
    * **Kalibre Edilmiş Ekonometri:** Göstergeler arasındaki yapay uçurumlar ve kutup karmaşaları tamamen giderilmiştir.
    * **Dengeli Tanh Dönüşümü:** Skorlar ne sıkışır ne de yapay olarak $\pm 90$'a patlar; makronun gerçek şiddetini yansıtır.
    """)
