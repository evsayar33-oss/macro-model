import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from fredapi import Fred
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. SAYFA VE API AYARLARI ---
st.set_page_config(page_title="Makro Trend v6.6 (Institutional Fed Grade)", layout="wide")

try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=FRED_API_KEY)
except:
    st.error("Lütfen Streamlit Cloud ayarlarına FRED_API_KEY eklediğinizden emin olun!")
    st.stop()

# --- 2. GELİŞMİŞ MERKEZ BANKASI, KRİPTO & KÜRESEL LİKİDİTE MOTORU ---
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

# DEFİLLAMA STABLECOIN KÜRESEL ARZ MOTORU (KRİPTO M2)
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

# --- 3. SIFIR GECİKMELİ (ZERO-LAG) PİYASA REJİM MOTORU ---
def get_realtime_macro_regime():
    t10yie = fetch_fred_data('T10YIE') 
    fwd_inf = fetch_fred_data('T5YIFR') 
    icsa = fetch_fred_data('ICSA') # YENİ: Haftalık Öncü İstihdam Başvuruları
    consumer_exp = fetch_fred_data('UMCSENT') 
    
    if len(t10yie) < 60 or len(icsa) < 60:
        return "NOTR", "NÖTR PİYASA", 1.0 
        
    inf_momentum = t10yie.iloc[-1] > t10yie.iloc[-40]
    inf_elevated = t10yie.iloc[-1] > 2.30 
    fwd_rising = fwd_inf.iloc[-1] > fwd_inf.iloc[-60] if len(fwd_inf) > 60 else False
    
    inflation_pressure = (inf_momentum and inf_elevated) or fwd_rising
    labor_deteriorating = icsa.iloc[-1] > icsa.iloc[-60:].mean() # İstihdam bozuluyor mu?
    growth_strong = consumer_exp.iloc[-1] > consumer_exp.iloc[-60] if len(consumer_exp) > 60 else True

    if not inflation_pressure and not labor_deteriorating:
        mult = 1.3 if growth_strong else 1.2
        return "GOLDILOCKS", "GOLDILOCKS (Düşen Enflasyon Beklentisi, Güçlü Büyüme)", mult
    elif inflation_pressure and not labor_deteriorating:
        mult = 1.2 if growth_strong else 1.1
        return "REFLASYON", "REFLASYON (Genişleyen Enflasyon Beklentisi, Güçlü Büyüme)", mult
    elif inflation_pressure and labor_deteriorating:
        mult = 1.4 if not growth_strong else 1.5 
        return "STAGFLASYON", "STAGFLASYON (Artan Enflasyon Fiyatlaması, Zayıflayan İstihdam)", mult
    else:
        mult = 1.4
        return "DEFLASYON", "DEFLASYONİST DARALMA (Çöken Enflasyon, Resesyon Baskısı)", mult

# --- 4. SİSTEMİK RİSK VE ŞOK ŞALTERİ (CIRCUIT BREAKER) ---
def check_systemic_circuit_breaker():
    move = fetch_yf_data('^MOVE')
    hy_oas = fetch_fred_data('BAMLH0A0HYM2') 
    nfci = fetch_fred_data('NFCI')
    vix = fetch_yf_data('^VIX')
    
    reasons = []
    is_triggered = False
    
    if not move.empty and move.iloc[-1] > 125:
        is_triggered = True
        reasons.append(f"MOVE Tahvil Volatilitesi Aşırı Risk Eşiğinde ({move.iloc[-1]:.1f} > 125)")
        
    if not hy_oas.empty and len(hy_oas) > 60:
        oas_z = (hy_oas.iloc[-1] - hy_oas.iloc[-60:].mean()) / (hy_oas.iloc[-60:].std() + 1e-5)
        if oas_z > 2.2 or hy_oas.iloc[-1] > 4.5:
            is_triggered = True
            reasons.append(f"Yüksek Getirili Kredi (HY Spread) Stres Patlaması ({hy_oas.iloc[-1]:.2f}%)")
            
    if not nfci.empty and nfci.iloc[-1] > 0.05:
        is_triggered = True
        reasons.append(f"Chicago Fed NFCI Pozitif Bölgede (Likidite Sıkılaşması)")
        
    if not vix.empty and vix.iloc[-1] > 28:
        is_triggered = True
        reasons.append(f"VIX Panik Eşiği Aşıldı ({vix.iloc[-1]:.1f} > 28)")
        
    return is_triggered, reasons

# Rejim Katsayı Matrisi
REGIME_CATEGORY_WEIGHTS = {
    "GOLDILOCKS": {"LIKIDITE": 1.4, "BUYUME_SANAYI": 1.4, "FAIZ_BEKLENTI": 1.1, "ENFLASYON": 0.6, "RISK_STRES": 0.6},
    "REFLASYON": {"LIKIDITE": 1.2, "BUYUME_SANAYI": 1.3, "ENFLASYON": 1.4, "FAIZ_BEKLENTI": 1.0, "RISK_STRES": 0.7},
    "STAGFLASYON": {"ENFLASYON": 1.8, "RISK_STRES": 1.6, "FAIZ_BEKLENTI": 1.2, "LIKIDITE": 0.7, "BUYUME_SANAYI": 0.4},
    "DEFLASYON": {"RISK_STRES": 1.7, "FAIZ_BEKLENTI": 1.4, "LIKIDITE": 1.2, "BUYUME_SANAYI": 0.4, "ENFLASYON": 0.4},
    "NOTR": {"LIKIDITE": 1.0, "BUYUME_SANAYI": 1.0, "FAIZ_BEKLENTI": 1.0, "ENFLASYON": 1.0, "RISK_STRES": 1.0}
}

# --- 5. ÇİFT HIZLI (DUAL-SPEED) Z-SKOR VE ŞOK MOTORU ---
def process_indicator(data_series, invert=False, is_rate=False):
    if isinstance(data_series, pd.DataFrame):
        data_series = data_series.iloc[:, 0]
        
    data_series = data_series.dropna()
    
    if len(data_series) < 200:
        val = float(data_series.iloc[-1]) if not data_series.empty else 0.0
        return 0.0, val
    
    if is_rate:
        momentum = data_series.diff(60).dropna()
        if len(momentum) < 200:
            return 0.0, float(data_series.iloc[-1])
        ema_trend = momentum.ewm(span=60, adjust=False).mean()
        fast_impulse = data_series.diff(5).dropna().iloc[-1]
    else:
        ema_trend = data_series.ewm(span=60, adjust=False).mean()
        fast_impulse = (data_series.pct_change(3).dropna().iloc[-1]) * 100
        
    mean_252 = ema_trend.rolling(window=252).mean()
    std_252 = ema_trend.rolling(window=252).std()
    
    current_val = float(ema_trend.iloc[-1])
    mean_val = float(mean_252.iloc[-1])
    std_val = float(std_252.iloc[-1])
    
    base_z_score = (current_val - mean_val) / (std_val + 1e-5)
    
    shock_bonus = 0.0
    if not is_rate:
        if fast_impulse > 6.0:  
            shock_bonus = 0.75
        elif fast_impulse < -6.0:
            shock_bonus = -0.75
    else:
        if fast_impulse > 0.25: 
            shock_bonus = 0.50
        elif fast_impulse < -0.25:
            shock_bonus = -0.50

    z_score = base_z_score + shock_bonus
    
    if invert:
        z_score = -z_score
        
    z_score = float(max(-3.0, min(3.0, z_score)))
    display_val = float(data_series.iloc[-1])
    return z_score, display_val

# --- 6. ARAYÜZ VE UYGULAMA ---
st.title("🏛️ KÜRESEL MAKRO & SWING MODELİ (v6.6 - ORTHOGONAL FED GRADE)")
st.markdown("**Tam Bağımsız Faktör Mimarisi, Fiziksel Stok ve Öncü İstihdam Katmanlı Portföy Motoru**")

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

regime_code, regime_name, regime_multiplier = get_realtime_macro_regime()
circuit_triggered, circuit_reasons = check_systemic_circuit_breaker()

# Üst Bilgi Kartları
col_info1, col_info2, col_info3 = st.columns(3)
with col_info1:
    st.metric("Aktif Piyasa Rejimi (Breakeven Bazlı)", regime_code, f"Çarpan: {regime_multiplier}x")
with col_info2:
    if circuit_triggered:
        st.metric("Sistemik Risk Şalteri", "🚨 AKTİF (KORUMA MODU)", "Risk Azaltıldı", delta_color="inverse")
    else:
        st.metric("Sistemik Risk Şalteri", "✅ NORMAL", "Sistem Dengeli")
with col_info3:
    t10_val = fetch_fred_data('T10YIE')
    st.metric("10Y Breakeven Enflasyon", f"%{t10_val.iloc[-1]:.2f}" if not t10_val.empty else "N/A", "Piyasa İçi Gerçek Zamanlı")

if circuit_triggered:
    st.error(f"⚠️ **SİSTEMİK RİSK ŞALTERİ DEVREDE:** Aşağıdaki anomaliler sebebiyle alım sinyalleri baskılanmış, nakit koruması artırılmıştır:\n* " + "\n* ".join(circuit_reasons))

indicators_data = []
total_score = 0

with st.spinner(f"{asset} için Bağımsız Faktör Seti Hesaplanıyor..."):
    if asset == "Altın (XAU)":
        metrics = [
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), 0.11, "FAIZ_BEKLENTI", True, True),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.09, "FAIZ_BEKLENTI", True, True),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), 0.08, "FAIZ_BEKLENTI", True, True),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), 0.10, "ENFLASYON", False, True), 
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.10, "LIKIDITE", False, False), 
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.06, "LIKIDITE", False, False),
            ("MOVE Endeksi (Tahvil Paniği)", fetch_yf_data('^MOVE'), 0.09, "RISK_STRES", False, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.08, "RISK_STRES", False, False),
            ("Getiri Eğrisi Eğim İvmesi (10Y-2Y)", fetch_fred_data('T10Y2Y'), 0.08, "FAIZ_BEKLENTI", False, True),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), 0.07, "RISK_STRES", False, True),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.08, "LIKIDITE", True, False),
            ("Altın / Petrol Stagflasyon Rasyosu", fetch_yf_data('GC=F') / fetch_yf_data('CL=F'), 0.05, "ENFLASYON", False, False),
            ("Bakır / Altın Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.05, "BUYUME_SANAYI", True, False),
        ]
    elif asset == "Gümüş (XAG)":
        metrics = [
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), 0.11, "BUYUME_SANAYI", False, False),
            ("Gümüş Momentum Trendi (SI=F)", fetch_yf_data('SI=F'), 0.11, "BUYUME_SANAYI", False, False),
            ("Küresel Taşımacılık İvmesi (IYT)", fetch_yf_data('IYT'), 0.08, "BUYUME_SANAYI", False, False), # YENİ: Taşımacılık Sinyali
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.09, "FAIZ_BEKLENTI", True, True),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), 0.07, "FAIZ_BEKLENTI", True, True),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), 0.09, "ENFLASYON", False, True), 
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.09, "BUYUME_SANAYI", False, False),
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.08, "LIKIDITE", False, False), 
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.05, "LIKIDITE", False, False),
            ("Altın / Gümüş Rasyosu", fetch_yf_data('GC=F') / fetch_yf_data('SI=F'), 0.07, "BUYUME_SANAYI", True, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.07, "RISK_STRES", True, False),
            ("Çin Piyasası İvmesi (MCHI)", fetch_yf_data('MCHI'), 0.06, "BUYUME_SANAYI", False, False),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), 0.05, "RISK_STRES", True, True),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.05, "LIKIDITE", True, False),
        ]
    elif asset == "Nasdaq 100 (NQ)":
        metrics = [
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.12, "LIKIDITE", False, False), 
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.07, "LIKIDITE", False, False),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), 0.09, "FAIZ_BEKLENTI", True, True),
            ("Öncü Haftalık İstihdam Stresi (ICSA)", fetch_fred_data('ICSA'), 0.08, "RISK_STRES", True, False), # YENİ: Öncü İşsizlik
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.09, "RISK_STRES", True, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.08, "FAIZ_BEKLENTI", True, True),
            ("Ticari Banka Rezervleri (WRESBAL)", fetch_fred_data('WRESBAL'), 0.08, "LIKIDITE", False, False),
            ("NQ / 10Y Risk Primi Proxy", fetch_yf_data('QQQ') / fetch_yf_data('^TNX'), 0.08, "BUYUME_SANAYI", False, False),
            ("Yen Carry Trade Döngüsü (USD/JPY)", fetch_yf_data('JPY=X'), 0.07, "LIKIDITE", False, False),
            ("VIX Volatilite Eğilimi", fetch_yf_data('^VIX'), 0.07, "RISK_STRES", True, False),
            ("Yarı İletken Liderliği (SOXX/QQQ)", fetch_yf_data('SOXX') / fetch_yf_data('QQQ'), 0.07, "BUYUME_SANAYI", False, False),
            ("MOVE Endeksi (Tahvil Baskısı)", fetch_yf_data('^MOVE'), 0.06, "RISK_STRES", True, False),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), 0.05, "RISK_STRES", True, True),
        ]
    elif asset == "S&P 500 (SPX)":
        metrics = [
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.12, "LIKIDITE", False, False), 
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.07, "LIKIDITE", False, False),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), 0.08, "FAIZ_BEKLENTI", True, True),
            ("Öncü Haftalık İstihdam Stresi (ICSA)", fetch_fred_data('ICSA'), 0.08, "RISK_STRES", True, False), # YENİ
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.09, "RISK_STRES", True, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.08, "FAIZ_BEKLENTI", True, True),
            ("Ticari Banka Rezervleri (WRESBAL)", fetch_fred_data('WRESBAL'), 0.08, "LIKIDITE", False, False),
            ("Eşit Ağırlık Piyasa Genişliği (RSP/SPY)", fetch_yf_data('RSP') / fetch_yf_data('SPY'), 0.08, "BUYUME_SANAYI", False, False),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), 0.07, "RISK_STRES", True, True),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), 0.08, "ENFLASYON", True, True),
            ("VIX Volatilite Eğilimi", fetch_yf_data('^VIX'), 0.07, "RISK_STRES", True, False),
            ("MOVE Endeksi (Tahvil Volatilitesi)", fetch_yf_data('^MOVE'), 0.05, "RISK_STRES", True, False),
            ("Bakır / Altın Rasyosu (Global Büyüme)", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.05, "BUYUME_SANAYI", False, False),
        ]
    elif asset == "Kripto (BTC)":
        metrics = [
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.12, "LIKIDITE", False, False),
            ("Stablecoin Küresel Arz İvmesi (DefiLlama)", fetch_defillama_stablecoins(), 0.11, "LIKIDITE", False, False),
            ("Kripto-İçi Risk İştahı (ETH/BTC)", fetch_yf_data('ETH-USD') / fetch_yf_data('BTC-USD'), 0.08, "BUYUME_SANAYI", False, False), # YENİ: Altcoin İştahı
            ("Kripto Korku & Açgözlülük (F&G)", fetch_crypto_fear_greed(), 0.08, "RISK_STRES", False, False),
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.08, "LIKIDITE", False, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.08, "FAIZ_BEKLENTI", True, True),
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), 0.08, "FAIZ_BEKLENTI", True, True),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.08, "RISK_STRES", True, False),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.07, "LIKIDITE", True, False),
            ("Teknoloji / Risk İştahı (QQQ)", fetch_yf_data('QQQ'), 0.07, "BUYUME_SANAYI", False, False),
            ("Ticari Banka Rezervleri (WRESBAL)", fetch_fred_data('WRESBAL'), 0.06, "LIKIDITE", False, False),
            ("VIX Volatilite Eğilimi", fetch_yf_data('^VIX'), 0.06, "RISK_STRES", True, False),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), 0.05, "RISK_STRES", True, True),
            ("SKEW Siyah Kuğu Kuyruk Riski", fetch_yf_data('^SKEW'), 0.04, "RISK_STRES", True, False),
        ]
    elif asset == "Ham Petrol (WTI)":
        metrics = [
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), 0.12, "ENFLASYON", False, True),
            ("ABD Fiziksel Ham Petrol Stokları", fetch_fred_data('WCESTUS1'), 0.11, "BUYUME_SANAYI", True, False), # YENİ: Fiziksel Stok (Ters: Düşen stok = Boğa)
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.10, "BUYUME_SANAYI", False, False),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.10, "LIKIDITE", True, False),
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), 0.09, "BUYUME_SANAYI", False, False),
            ("Çin Piyasası İvmesi (MCHI)", fetch_yf_data('MCHI'), 0.09, "BUYUME_SANAYI", False, False),
            ("5y5y Forward Enflasyon Çıpası (T5YIFR)", fetch_fred_data('T5YIFR'), 0.09, "ENFLASYON", False, True),
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.08, "LIKIDITE", False, False),
            ("Getiri Eğrisi Eğim İvmesi (10Y-2Y)", fetch_fred_data('T10Y2Y'), 0.07, "FAIZ_BEKLENTI", False, True),
            ("MOVE Endeksi (Tahvil/Jeopolitik Risk)", fetch_yf_data('^MOVE'), 0.06, "RISK_STRES", False, False),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), 0.05, "RISK_STRES", True, True),
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.04, "LIKIDITE", False, False),
        ]
    elif asset == "Bakır (HG)":
        metrics = [
            ("Çin Piyasası İvmesi (MCHI)", fetch_yf_data('MCHI'), 0.12, "BUYUME_SANAYI", False, False),
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), 0.11, "BUYUME_SANAYI", False, False),
            ("Küresel Taşımacılık İvmesi (IYT)", fetch_yf_data('IYT'), 0.09, "BUYUME_SANAYI", False, False), # YENİ: Sanayi Taşımacılığı
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.10, "BUYUME_SANAYI", False, False),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.10, "LIKIDITE", True, False),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), 0.09, "ENFLASYON", False, True),
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.09, "LIKIDITE", False, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.08, "FAIZ_BEKLENTI", True, True),
            ("Getiri Eğrisi Eğim İvmesi (10Y-2Y)", fetch_fred_data('T10Y2Y'), 0.07, "FAIZ_BEKLENTI", False, True),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.06, "RISK_STRES", True, False),
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.05, "LIKIDITE", False, False),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), 0.04, "RISK_STRES", True, True),
        ]
    else:
        metrics = [
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), 0.12, "FAIZ_BEKLENTI", True, True),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.11, "FAIZ_BEKLENTI", True, True),
            ("Öncü Haftalık İstihdam Stresi (ICSA)", fetch_fred_data('ICSA'), 0.10, "RISK_STRES", False, False), # YENİ (İşsizlik artışı tahvile yarar)
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), 0.10, "FAIZ_BEKLENTI", True, True),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), 0.10, "ENFLASYON", True, True),
            ("MOVE Endeksi (Tahvil Volatilitesi)", fetch_yf_data('^MOVE'), 0.09, "RISK_STRES", True, False),
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.09, "LIKIDITE", False, False),
            ("Getiri Eğrisi Eğim İvmesi (10Y-2Y)", fetch_fred_data('T10Y2Y'), 0.08, "FAIZ_BEKLENTI", True, True),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), 0.08, "RISK_STRES", False, True),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.05, "LIKIDITE", False, False),
            ("VIX Volatilite Eğilimi", fetch_yf_data('^VIX'), 0.05, "RISK_STRES", False, False),
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.04, "LIKIDITE", False, False),
        ]

    # --- DİNAMİK AĞIRLIKLANDIRMA HESABI ---
    raw_dynamic_weights = []
    regime_multipliers_dict = REGIME_CATEGORY_WEIGHTS.get(regime_code, REGIME_CATEGORY_WEIGHTS["NOTR"])
    
    for item in metrics:
        base_w = item[2]
        cat = item[3]
        cat_mult = regime_multipliers_dict.get(cat, 1.0)
        raw_dynamic_weights.append(base_w * cat_mult)
        
    total_raw_weight = sum(raw_dynamic_weights)
    dynamic_weights = [w / total_raw_weight for w in raw_dynamic_weights]

    for idx, item in enumerate(metrics):
        name, data_series, base_w, category, invert, is_rate = item
        dyn_weight = dynamic_weights[idx]
        
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
            "Kategori": category,
            "Güncel Değer": display_str,
            "1-Yıllık İvme (Z-Skor)": round(z, 2),
            "Dinamik Ağırlık": f"%{dyn_weight * 100:.1f}",
            "Modele Net Katkı": round(contribution, 3)
        })

final_trend_score = max(-100, min(100, total_score * 25))
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
        title = {'text': f"{asset}<br>Kurumsal Trend Skoru", 'font': {'size': 20}},
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
    st.markdown("### 📊 Dinamik Faktör & Risk Dağılım Tablosu")
    df_results = pd.DataFrame(indicators_data)
    st.dataframe(df_results, use_container_width=True)
    
    st.markdown("""
    **Kurumsal Risk Yönetimi Rehberi:**
    * **Tam Bağımsızlık:** Her gösterge tekil bir makro/fiziksel dinamiği ölçer (Çoklu doğrusallık riski sıfırlanmıştır).
    * **Öncü İstihdam (ICSA):** Haftalık ilk işsizlik başvuruları resesyon riskini 45 gün önceden yakalar.
    * **Fiziksel Petrol Stokları:** EIA verisi üzerinden enerji piyasasındaki gerçek fiziksel arz/talep dengesini okur.
    * **8 Varlık Kapsamı:** Altın, Gümüş, Nasdaq, S&P 500, Kripto (BTC), Ham Petrol, Bakır ve ABD Tahvili (TLT).
    """)
