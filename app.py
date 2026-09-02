import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from fredapi import Fred
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. SAYFA VE API AYARLARI ---
st.set_page_config(page_title="Makro Trend v9.0 (Ultra-Quant Fed Grade)", layout="wide")

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

# Rejim Katsayı Matrisi
REGIME_CATEGORY_WEIGHTS = {
    "GOLDILOCKS": {"LIKIDITE": 1.3, "BUYUME_SANAYI": 1.3, "FAIZ_BEKLENTI": 1.1, "ENFLASYON": 0.7, "RISK_STRES": 0.7},
    "REFLASYON": {"LIKIDITE": 1.2, "BUYUME_SANAYI": 1.4, "ENFLASYON": 1.4, "FAIZ_BEKLENTI": 1.0, "RISK_STRES": 0.7},
    "STAGFLASYON": {"ENFLASYON": 1.6, "RISK_STRES": 1.5, "FAIZ_BEKLENTI": 1.2, "LIKIDITE": 0.8, "BUYUME_SANAYI": 0.5},
    "DEFLASYON": {"RISK_STRES": 1.6, "FAIZ_BEKLENTI": 1.4, "LIKIDITE": 1.2, "BUYUME_SANAYI": 0.5, "ENFLASYON": 0.5},
    "NOTR": {"LIKIDITE": 1.0, "BUYUME_SANAYI": 1.0, "FAIZ_BEKLENTI": 1.0, "ENFLASYON": 1.0, "RISK_STRES": 1.0}
}

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

# --- 5. GELİŞMİŞ KURUMSAL Z-SKOR MOTORU (ÇİFT YUMUŞATMA HATASI GİDERİLDİ) ---
def process_indicator(data_series, invert=False, is_rate=False):
    if isinstance(data_series, pd.DataFrame):
        data_series = data_series.iloc[:, 0]
        
    data_series = data_series.dropna()
    
    if len(data_series) < 150:
        val = float(data_series.iloc[-1]) if not data_series.empty else 0.0
        return 0.0, val
    
    current_val = float(data_series.iloc[-1])
    
    if is_rate:
        # Faiz ve Oranlar için: Son 40 günlük net değişim + 252 günlük seviye konumu
        delta_40 = data_series.diff(40).dropna()
        mean_delta = delta_40.rolling(window=252).mean().iloc[-1]
        std_delta = delta_40.rolling(window=252).std().iloc[-1]
        
        z_momentum = (delta_40.iloc[-1] - mean_delta) / (std_delta + 1e-5)
        
        # Seviye konumu (Level Z-Score)
        mean_level = data_series.rolling(window=252).mean().iloc[-1]
        std_level = data_series.rolling(window=252).std().iloc[-1]
        z_level = (current_val - mean_level) / (std_level + 1e-5)
        
        base_z_score = 0.6 * z_momentum + 0.4 * z_level
        fast_impulse = data_series.diff(5).dropna().iloc[-1] if len(data_series) > 5 else 0.0
    else:
        # Fiyat ve Rasyolar için: 40G EMA'nın 252G Bant Konumu
        ema_40 = data_series.ewm(span=40, adjust=False).mean()
        mean_252 = ema_40.rolling(window=252).mean().iloc[-1]
        std_252 = data_series.rolling(window=252).std().iloc[-1] # Ham standart sapma ile gerçek volatilite
        
        base_z_score = (ema_40.iloc[-1] - mean_252) / (std_252 + 1e-5)
        fast_impulse = (data_series.pct_change(3).dropna().iloc[-1]) * 100 if len(data_series) > 3 else 0.0
        
    # Hızlı Şok Sensörü (Exogenous Shock Filter)
    shock_bonus = 0.0
    if not is_rate:
        if fast_impulse > 5.0:  
            shock_bonus = 0.60
        elif fast_impulse < -5.0:
            shock_bonus = -0.60
    else:
        if fast_impulse > 0.18: 
            shock_bonus = 0.40
        elif fast_impulse < -0.18:
            shock_bonus = -0.40

    z_score = base_z_score + shock_bonus
    
    if invert:
        z_score = -z_score
        
    z_score = float(max(-3.0, min(3.0, z_score)))
    display_val = current_val
    return z_score, display_val

# --- 6. ARAYÜZ VE UYGULAMA ---
st.title("🏛️ KÜRESEL MAKRO MODELİ (v9.0 - ULTRA-QUANT GRADE)")
st.markdown("**Doğrusal Olmayan (Tanh) Makro Dinamik Mimarisi & Saf Yapısal Portföy Motoru**")

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

with st.spinner(f"{asset} için Saf Makro Faktörler Hesaplanıyor..."):
    if asset == "Altın (XAU)":
        # Altın için Mali Borç Genişlemesi ve Dolar Devalüasyonu eklendi (Altın-Gümüş ayrışması çözüldü)
        metrics = [
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), 0.14, "FAIZ_BEKLENTI", True, True),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), 0.13, "ENFLASYON", False, True), 
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.12, "LIKIDITE", False, False), 
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.11, "FAIZ_BEKLENTI", True, True),
            ("Bakır / Altın Rasyosu (Ters Döngü)", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.10, "BUYUME_SANAYI", True, False), # YENİ: Altının lehine çalışan ters döngü
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.10, "LIKIDITE", True, False),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), 0.09, "FAIZ_BEKLENTI", True, True),
            ("MOVE Endeksi (Tahvil/Jeopolitik Panik)", fetch_yf_data('^MOVE'), 0.08, "RISK_STRES", False, False),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), 0.07, "RISK_STRES", False, True),
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.06, "LIKIDITE", False, False),
        ]
    elif asset == "Gümüş (XAG)":
        metrics = [
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), 0.14, "BUYUME_SANAYI", False, False),
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.13, "BUYUME_SANAYI", False, False),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), 0.12, "ENFLASYON", False, True), 
            ("Küresel Taşımacılık İvmesi (IYT)", fetch_yf_data('IYT'), 0.11, "BUYUME_SANAYI", False, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.10, "FAIZ_BEKLENTI", True, True),
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.10, "LIKIDITE", False, False), 
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.09, "LIKIDITE", True, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.08, "RISK_STRES", True, False),
            ("Altın / Gümüş Değerleme Rasyosu", fetch_yf_data('GC=F') / fetch_yf_data('SI=F'), 0.07, "BUYUME_SANAYI", True, False),
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.06, "LIKIDITE", False, False),
        ]
    elif asset == "Nasdaq 100 (NQ)":
        metrics = [
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.14, "LIKIDITE", False, False), 
            ("Yarı İletken Liderliği (SOXX/QQQ)", fetch_yf_data('SOXX') / fetch_yf_data('QQQ'), 0.13, "BUYUME_SANAYI", False, False),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), 0.11, "FAIZ_BEKLENTI", True, True),
            ("Öncü Haftalık İstihdam Stresi (ICSA)", fetch_fred_data('ICSA'), 0.11, "RISK_STRES", True, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.10, "RISK_STRES", True, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.10, "FAIZ_BEKLENTI", True, True),
            ("Ticari Banka Rezervleri (WRESBAL)", fetch_fred_data('WRESBAL'), 0.09, "LIKIDITE", False, False),
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.08, "LIKIDITE", False, False),
            ("Yen Carry Trade Döngüsü (USD/JPY)", fetch_yf_data('JPY=X'), 0.08, "LIKIDITE", False, False),
            ("VIX Volatilite Eğilimi", fetch_yf_data('^VIX'), 0.06, "RISK_STRES", True, False),
        ]
    elif asset == "S&P 500 (SPX)":
        metrics = [
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.13, "LIKIDITE", False, False), 
            ("Eşit Ağırlık Piyasa Genişliği (RSP/SPY)", fetch_yf_data('RSP') / fetch_yf_data('SPY'), 0.12, "BUYUME_SANAYI", False, False),
            ("Öncü Haftalık İstihdam Stresi (ICSA)", fetch_fred_data('ICSA'), 0.11, "RISK_STRES", True, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.11, "RISK_STRES", True, False),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), 0.10, "FAIZ_BEKLENTI", True, True),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.10, "FAIZ_BEKLENTI", True, True),
            ("Ticari Banka Rezervleri (WRESBAL)", fetch_fred_data('WRESBAL'), 0.09, "LIKIDITE", False, False),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), 0.09, "RISK_STRES", True, True),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), 0.08, "ENFLASYON", True, True),
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.07, "LIKIDITE", False, False),
        ]
    elif asset == "Kripto (BTC)":
        metrics = [
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.15, "LIKIDITE", False, False),
            ("Stablecoin Küresel Arz İvmesi (DefiLlama)", fetch_defillama_stablecoins(), 0.14, "LIKIDITE", False, False),
            ("Kripto-İçi Risk İştahı (ETH/BTC)", fetch_yf_data('ETH-USD') / fetch_yf_data('BTC-USD'), 0.12, "BUYUME_SANAYI", False, False),
            ("Kripto Korku & Açgözlülük (F&G)", fetch_crypto_fear_greed(), 0.11, "RISK_STRES", False, False),
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), 0.10, "FAIZ_BEKLENTI", True, True),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.10, "FAIZ_BEKLENTI", True, True),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.09, "RISK_STRES", True, False),
            ("Hızlı Likidite İvmesi (5G Hazine Hızı)", fetch_global_net_liquidity().diff(5), 0.08, "LIKIDITE", False, False),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.06, "LIKIDITE", True, False),
            ("Ticari Banka Rezervleri (WRESBAL)", fetch_fred_data('WRESBAL'), 0.05, "LIKIDITE", False, False),
        ]
    elif asset == "Ham Petrol (WTI)":
        # 1 Varil = 42 Galon. Crack Spread doğru $/Varil olarak hesaplandı.
        gasoline_bbl = fetch_yf_data('RB=F') * 42.0
        heating_oil_bbl = fetch_yf_data('HO=F') * 42.0
        crude_bbl = fetch_yf_data('CL=F')
        brent_bbl = fetch_yf_data('BZ=F')
        dbc_commodities = fetch_yf_data('DBC')
        
        crack_spread = ((2 * gasoline_bbl + 1 * heating_oil_bbl) / 3) - crude_bbl
        brent_wti_spread = brent_bbl - crude_bbl
        oil_commodity_ratio = crude_bbl / dbc_commodities

        metrics = [
            ("Rafineri Çatlak Marjı (Fiziki Talep)", crack_spread, 0.16, "BUYUME_SANAYI", False, False),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), 0.14, "ENFLASYON", False, True),
            ("Küresel Fiziki Arz Açığı (Brent/WTI)", brent_wti_spread, 0.13, "BUYUME_SANAYI", False, False),
            ("Enerji / Emtia Rotasyon Gücü", oil_commodity_ratio, 0.12, "BUYUME_SANAYI", False, False),
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.11, "BUYUME_SANAYI", False, False),
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), 0.10, "BUYUME_SANAYI", False, False),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.09, "LIKIDITE", True, False),
            ("5y5y Forward Enflasyon Çıpası (T5YIFR)", fetch_fred_data('T5YIFR'), 0.08, "ENFLASYON", False, True),
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.07, "LIKIDITE", False, False),
        ]
    elif asset == "Bakır (HG)":
        metrics = [
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), 0.15, "BUYUME_SANAYI", False, False),
            ("Küresel Taşımacılık İvmesi (IYT)", fetch_yf_data('IYT'), 0.13, "BUYUME_SANAYI", False, False),
            ("Bakır / Petrol Sanayi Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('CL=F'), 0.12, "BUYUME_SANAYI", False, False),
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.12, "BUYUME_SANAYI", False, False),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), 0.11, "ENFLASYON", False, True),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.10, "LIKIDITE", True, False),
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.10, "LIKIDITE", False, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.09, "FAIZ_BEKLENTI", True, True),
            ("Getiri Eğrisi Eğim İvmesi (10Y-2Y)", fetch_fred_data('T10Y2Y'), 0.08, "FAIZ_BEKLENTI", False, True),
        ]
    else:
        # ABD TAHVİLİ / FAİZ (TLT) - İSTİHDAM VE FAİZ İNDİRİM GÜCÜ ARTIRILDI
        metrics = [
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.15, "FAIZ_BEKLENTI", True, True),
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), 0.14, "FAIZ_BEKLENTI", True, True),
            ("Öncü Haftalık İstihdam Stresi (ICSA)", fetch_fred_data('ICSA'), 0.13, "RISK_STRES", False, False),
            ("Getiri Eğrisi Eğim İvmesi (10Y-2Y)", fetch_fred_data('T10Y2Y'), 0.12, "FAIZ_BEKLENTI", True, True),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), 0.11, "ENFLASYON", True, True),
            ("Hazine Süre/Borçlanma Riski (30Y Yield)", fetch_fred_data('DGS30'), 0.10, "FAIZ_BEKLENTI", True, True),
            ("Küresel Dolar Likiditesi (Fed + ECB)", fetch_global_net_liquidity(), 0.09, "LIKIDITE", False, False),
            ("MOVE Endeksi (Tahvil Volatilitesi)", fetch_yf_data('^MOVE'), 0.08, "RISK_STRES", True, False),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), 0.08, "RISK_STRES", False, True),
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

# DOĞRUSAL OLMAYAN (TANH) SKOR DÖNÜŞÜMÜ (SIKIŞIKLIK HATASI GİDERİLDİ)
raw_portfolio_score = total_score
final_trend_score = float(np.tanh(raw_portfolio_score / 0.45) * 100.0)
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
        title = {'text': f"{asset}<br>Ultra-Quant Makro Skoru", 'font': {'size': 20}},
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
    st.markdown("### 📊 Ultra-Quant Faktör Dağılım Tablosu")
    df_results = pd.DataFrame(indicators_data)
    st.dataframe(df_results, use_container_width=True)
    
    st.markdown("""
    **Kurumsal Ultra-Quant Rehberi:**
    * **Tanh (Hiperbolik Tanjant) Skorlama:** Sinyal sıkışması giderilmiş; makro rüzgarın gerçek şiddeti tam ölçekte göstergeye yansıtılmıştır.
    * **Saf Ekonometrik Z-Skor:** Çift yumuşatma kaldırılmış, seviye ve momentum ayrımı yapılmıştır.
    * **Fiziki Crack Spread:** Ham petrolün fiziki rafineri çekim gücü $/Varil dönüşümüyle tam kalibre edilmiştir.
    """)
