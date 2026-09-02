import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from fredapi import Fred
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. SAYFA VE API AYARLARI ---
st.set_page_config(page_title="Makro Trend v14.0 (True Global Macro Grade)", layout="wide")

try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=FRED_API_KEY)
except:
    st.error("Lütfen Streamlit Cloud ayarlarına FRED_API_KEY eklediğinizden emin olun!")
    st.stop()

# --- 2. G4 MERKEZ BANKALARI & TAM KÜRESEL LİKİDİTE MOTORU ---
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

# G4 TAM KÜRESEL NET LİKİDİTE MOTORU: (Fed Net + ECB USD + BoJ USD + PBoC İmpulsu)
@st.cache_data(ttl=1800)
def fetch_g4_global_net_liquidity(days=2500):
    try:
        walcl = fetch_fred_data('WALCL', days)       # Fed Bilançosu
        tga = fetch_fred_data('WTREGEN', days)       # ABD Hazine Hesabı
        rrp = fetch_fred_data('RRPONTSYD', days)     # Ters Repo
        ecb = fetch_fred_data('ECBASSETSW', days)   # ECB Bilançosu (EUR)
        eurusd = fetch_yf_data('EURUSD=X', days)     # EUR/USD
        usdjpy = fetch_yf_data('JPY=X', days)       # USD/JPY
        mchi = fetch_yf_data('MCHI', days)           # Çin Kredi/Piyasa İmpulsu Proxy
        
        df = pd.DataFrame({
            'w': walcl, 
            't': tga, 
            'r': rrp * 1000,
            'ecb': ecb,
            'eur': eurusd,
            'jpy': usdjpy,
            'cn': mchi
        }).dropna()
        
        # 1. ABD Net Likiditesi
        us_net = df['w'] - df['t'] - df['r']
        
        # 2. Avrupa ECB Likiditesi (Dolarlaştırılmış)
        ecb_usd = df['ecb'] * df['eur']
        
        # 3. Japonya BoJ Carry Likidite Faktörü (Yen Zayıflığı = Küresel Likidite Genişlemesi)
        boj_liquidity_impulse = (df['jpy'] / df['jpy'].rolling(252).mean()) * 2000000.0
        
        # 4. Çin Asya İmpulsu
        china_impulse = (df['cn'] / df['cn'].rolling(252).mean()) * 1500000.0
        
        # G4 Toplam Küresel Likidite Havuzu (Milyon $)
        g4_total = us_net + (ecb_usd * 0.35) + (boj_liquidity_impulse * 0.25) + (china_impulse * 0.20)
        return g4_total.resample('B').ffill().dropna()
    except:
        walcl = fetch_fred_data('WALCL', days)
        tga = fetch_fred_data('WTREGEN', days)
        rrp = fetch_fred_data('RRPONTSYD', days)
        df = pd.DataFrame({'w': walcl, 't': tga, 'r': rrp * 1000}).dropna()
        return (df['w'] - df['t'] - df['r']).resample('B').ffill().dropna()

# --- 3. KÜRESEL MALİYET, NAVLUN & REEL GETİRİ REJİM MOTORU ---
def get_realtime_macro_regime():
    t10yie = fetch_fred_data('T10YIE') 
    real_rate = fetch_fred_data('DFII10') 
    icsa = fetch_fred_data('ICSA') 
    consumer_exp = fetch_fred_data('UMCSENT') 
    
    bdry = fetch_yf_data('BDRY') # Baltic Dry Gemi Taşımacılığı
    dbc = fetch_yf_data('DBC')   # Geniş Emtia Sepeti
    
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
        return "GOLDILOCKS", "GOLDILOCKS (Düşen Küresel Maliyetler, Canlı Büyüme)", mult, inf_dynamic_anchor
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

# --- 5. EKONOMETRİK DENGELİ İVME MOTORU ---
def process_indicator(data_series, invert=False, is_rate=False):
    if isinstance(data_series, pd.DataFrame):
        data_series = data_series.iloc[:, 0]
        
    data_series = data_series.dropna()
    
    if len(data_series) < 80:
        val = float(data_series.iloc[-1]) if not data_series.empty else 0.0
        return 0.0, val
    
    current_val = float(data_series.iloc[-1])
    
    if is_rate:
        delta_30 = data_series.diff(30).dropna()
        delta_90 = data_series.diff(90).dropna()
        
        std_30 = delta_30.rolling(window=252).std().iloc[-1] if len(delta_30) >= 252 else delta_30.std()
        std_90 = delta_90.rolling(window=252).std().iloc[-1] if len(delta_90) >= 252 else delta_90.std()
        
        z_30 = (delta_30.iloc[-1]) / (std_30 + 1e-5) if std_30 > 0 else 0.0
        z_90 = (delta_90.iloc[-1]) / (std_90 + 1e-5) if std_90 > 0 else 0.0
        
        base_z_score = 0.6 * z_30 + 0.4 * z_90
    else:
        ema_30 = data_series.ewm(span=30, adjust=False).mean()
        mean_180 = data_series.rolling(window=180).mean().iloc[-1] if len(data_series) >= 180 else data_series.mean()
        std_180 = data_series.rolling(window=180).std().iloc[-1] if len(data_series) >= 180 else data_series.std()
        base_z_score = (ema_30.iloc[-1] - mean_180) / (std_180 + 1e-5)
        
    if invert:
        base_z_score = -base_z_score
        
    z_score = float(max(-2.5, min(2.5, base_z_score)))
    display_val = current_val
    return z_score, display_val

# --- 6. ARAYÜZ VE UYGULAMA ---
st.title("🏛️ KÜRESEL MAKRO MODELİ (v14.0 - TRUE GLOBAL MACRO)")
st.markdown("**G4 Süper Likidite (Fed+ECB+BoJ+Çin), Gemi Taşımacılığı (Baltic Dry) ve Küresel Faiz Arbitrajı**")

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
    bdry_val = fetch_yf_data('BDRY')
    st.metric("10Y Breakeven Enflasyon", f"%{t10_val.iloc[-1]:.2f}" if not t10_val.empty else "N/A", f"Baltic Dry Navlun: {bdry_val.iloc[-1]:.1f}" if not bdry_val.empty else "N/A")

if circuit_triggered:
    st.error(f"⚠️ **SİSTEMİK RİSK ŞALTERİ DEVREDE:** Aşağıdaki dinamik persentil kırılımları sebebiyle alım sinyalleri baskılanmıştır:\n* " + "\n* ".join(circuit_reasons))

indicators_data = []
total_score = 0

with st.spinner(f"{asset} için G4 Süper Likidite, Navlun ve Küresel Faizler Hesaplanıyor..."):
    # Format: (Gösterge Adı, Data, Ağırlık Sözlüğü {GOLDILOCKS, REFLASYON, STAGFLASYON, DEFLASYON}, TersMi, FaizMi)
    
    if asset == "Altın (XAU)":
        metrics_spec = [
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.24, "REFLASYON": 0.20, "STAGFLASYON": 0.18, "DEFLASYON": 0.24}, True, True),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.20, "STAGFLASYON": 0.24, "DEFLASYON": 0.08}, False, True), 
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ+Çin)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.14, "DEFLASYON": 0.20}, False, False), # YENİ: G4 Havuzu
            ("Küresel Deniz Ticareti/Navlun (BDRY)", fetch_yf_data('BDRY'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.14, "STAGFLASYON": 0.16, "DEFLASYON": 0.06}, False, False), 
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.14, "REFLASYON": 0.12, "STAGFLASYON": 0.08, "DEFLASYON": 0.14}, True, False),
            ("MOVE Endeksi (Tahvil/Jeopolitik Panik)", fetch_yf_data('^MOVE'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.12, "DEFLASYON": 0.10}, False, False),
            ("5y5y Forward Enflasyon Çıpası", fetch_fred_data('T5YIFR'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.10, "DEFLASYON": 0.04}, False, True),
            ("Yen Carry Arbitrajı (USD/JPY)", fetch_yf_data('JPY=X'), {"GOLDILOCKS": 0.06, "REFLASYON": 0.02, "STAGFLASYON": -0.02, "DEFLASYON": 0.04}, False, False),
        ]
    elif asset == "Gümüş (XAG)":
        metrics_spec = [
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.20, "REFLASYON": 0.18, "STAGFLASYON": 0.14, "DEFLASYON": 0.20}, True, True),
            ("Küresel Deniz Ticareti/Navlun (BDRY)", fetch_yf_data('BDRY'), {"GOLDILOCKS": 0.16, "REFLASYON": 0.18, "STAGFLASYON": 0.12, "DEFLASYON": 0.06}, False, False), 
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False, False),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.16, "STAGFLASYON": 0.20, "DEFLASYON": 0.08}, False, True), 
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), {"GOLDILOCKS": 0.14, "REFLASYON": 0.14, "STAGFLASYON": 0.06, "DEFLASYON": 0.06}, False, False),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ+Çin)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.12, "REFLASYON": 0.10, "STAGFLASYON": 0.10, "DEFLASYON": 0.14}, False, False), 
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.08, "STAGFLASYON": 0.06, "DEFLASYON": 0.10}, True, False),
        ]
    elif asset == "Nasdaq 100 (NQ)":
        metrics_spec = [
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.24, "REFLASYON": 0.22, "STAGFLASYON": 0.18, "DEFLASYON": 0.26}, True, True),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ+Çin)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.20, "REFLASYON": 0.18, "STAGFLASYON": 0.12, "DEFLASYON": 0.18}, False, False), 
            ("Yarı İletken Liderliği (SOXX/QQQ)", fetch_yf_data('SOXX') / fetch_yf_data('QQQ'), {"GOLDILOCKS": 0.16, "REFLASYON": 0.14, "STAGFLASYON": 0.06, "DEFLASYON": 0.06}, False, False),
            ("Yen Carry Arbitrajı (USD/JPY)", fetch_yf_data('JPY=X'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.08, "DEFLASYON": 0.10}, False, False), # YENİ: Asya Likiditesi
            ("Öncü Haftalık İstihdam Stresi (ICSA)", fetch_fred_data('ICSA'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.16, "DEFLASYON": 0.16}, True, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.14, "DEFLASYON": 0.14}, True, False),
            ("MOVE Endeksi (Tahvil Baskısı)", fetch_yf_data('^MOVE'), {"GOLDILOCKS": 0.04, "REFLASYON": 0.06, "STAGFLASYON": 0.10, "DEFLASYON": 0.06}, True, False),
            ("VIX Volatilite Eğilimi", fetch_yf_data('^VIX'), {"GOLDILOCKS": 0.04, "REFLASYON": 0.08, "STAGFLASYON": 0.18, "DEFLASYON": 0.08}, True, False),
        ]
    elif asset == "S&P 500 (SPX)":
        metrics_spec = [
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.22, "REFLASYON": 0.20, "STAGFLASYON": 0.16, "DEFLASYON": 0.24}, True, True),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ+Çin)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.12, "DEFLASYON": 0.18}, False, False), 
            ("Eşit Ağırlık Piyasa Genişliği (RSP/SPY)", fetch_yf_data('RSP') / fetch_yf_data('SPY'), {"GOLDILOCKS": 0.16, "REFLASYON": 0.15, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False, False),
            ("Öncü Haftalık İstihdam Stresi (ICSA)", fetch_fred_data('ICSA'), {"GOLDILOCKS": 0.14, "REFLASYON": 0.12, "STAGFLASYON": 0.16, "DEFLASYON": 0.16}, True, False),
            ("Küresel Taşımacılık / Lojistik (IYT)", fetch_yf_data('IYT'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), {"GOLDILOCKS": 0.10, "REFLASYON": 0.11, "STAGFLASYON": 0.14, "DEFLASYON": 0.14}, True, False),
            ("Yüksek Getirili Kredi Stresi (HY OAS)", fetch_fred_data('BAMLH0A0HYM2'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.10, "STAGFLASYON": 0.14, "DEFLASYON": 0.12}, True, True),
        ]
    elif asset == "Kripto (BTC)":
        metrics_spec = [
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ+Çin)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.24, "REFLASYON": 0.22, "STAGFLASYON": 0.14, "DEFLASYON": 0.22}, False, False),
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.20, "REFLASYON": 0.18, "STAGFLASYON": 0.14, "DEFLASYON": 0.20}, True, True),
            ("Stablecoin Küresel Arz İvmesi (DefiLlama)", fetch_defillama_stablecoins(), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.14, "DEFLASYON": 0.16}, False, False),
            ("Kripto-İçi Risk İştahı (ETH/BTC)", fetch_yf_data('ETH-USD') / fetch_yf_data('BTC-USD'), {"GOLDILOCKS": 0.14, "REFLASYON": 0.14, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False, False),
            ("Kripto Korku & Açgözlülük (F&G)", fetch_crypto_fear_greed(), {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.14, "DEFLASYON": 0.12}, False, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.10, "STAGFLASYON": 0.14, "DEFLASYON": 0.12}, True, False),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.04, "REFLASYON": 0.08, "STAGFLASYON": 0.08, "DEFLASYON": 0.12}, True, False),
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
            ("Rafineri Çatlak Marjı (Fiziki Talep)", crack_spread, {"GOLDILOCKS": 0.16, "REFLASYON": 0.22, "STAGFLASYON": 0.20, "DEFLASYON": 0.10}, False, False),
            ("Küresel Deniz Ticareti/Navlun (BDRY)", fetch_yf_data('BDRY'), {"GOLDILOCKS": 0.14, "REFLASYON": 0.18, "STAGFLASYON": 0.16, "DEFLASYON": 0.08}, False, False), 
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.18, "STAGFLASYON": 0.20, "DEFLASYON": 0.08}, False, True),
            ("Küresel Fiziki Arz Açığı (Brent/WTI)", brent_wti_spread, {"GOLDILOCKS": 0.14, "REFLASYON": 0.16, "STAGFLASYON": 0.18, "DEFLASYON": 0.10}, False, False),
            ("Doğal Gaz Enerji İvmesi (NG)", natgas, {"GOLDILOCKS": 0.10, "REFLASYON": 0.12, "STAGFLASYON": 0.14, "DEFLASYON": 0.06}, False, False), 
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.10, "DEFLASYON": 0.14}, True, True),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ+Çin)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.10, "REFLASYON": 0.10, "STAGFLASYON": 0.08, "DEFLASYON": 0.10}, False, False),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.06, "REFLASYON": 0.06, "STAGFLASYON": 0.06, "DEFLASYON": 0.10}, True, False),
        ]
    elif asset == "Bakır (HG)":
        metrics_spec = [
            ("Küresel Deniz Ticareti/Navlun (BDRY)", fetch_yf_data('BDRY'), {"GOLDILOCKS": 0.22, "REFLASYON": 0.22, "STAGFLASYON": 0.12, "DEFLASYON": 0.08}, False, False), 
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), {"GOLDILOCKS": 0.20, "REFLASYON": 0.18, "STAGFLASYON": 0.10, "DEFLASYON": 0.08}, False, False),
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), {"GOLDILOCKS": 0.18, "REFLASYON": 0.16, "STAGFLASYON": 0.08, "DEFLASYON": 0.06}, False, False),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ+Çin)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.14, "REFLASYON": 0.14, "STAGFLASYON": 0.10, "DEFLASYON": 0.14}, False, False),
            ("Reel Faiz İskonto Çıpası (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.12, "STAGFLASYON": 0.12, "DEFLASYON": 0.16}, True, True),
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.08, "REFLASYON": 0.12, "STAGFLASYON": 0.16, "DEFLASYON": 0.06}, False, True),
            ("Dolar Endeksi Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), {"GOLDILOCKS": 0.06, "REFLASYON": 0.06, "STAGFLASYON": 0.06, "DEFLASYON": 0.08}, True, False),
        ]
    else:
        # ABD TAHVİLİ / FAİZ (TLT) - G4 LİKİDİTE, REEL GETİRİ VE ENFLASYON İNDİRGEME ÇIPASI
        metrics_spec = [
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), {"GOLDILOCKS": 0.28, "REFLASYON": 0.26, "STAGFLASYON": 0.22, "DEFLASYON": 0.30}, True, True),
            ("Öncü Haftalık İstihdam Stresi (ICSA)", fetch_fred_data('ICSA'), {"GOLDILOCKS": 0.20, "REFLASYON": 0.18, "STAGFLASYON": 0.24, "DEFLASYON": 0.26}, False, False), 
            ("Getiri Eğrisi Eğim İvmesi (10Y-2Y)", fetch_fred_data('T10Y2Y'), {"GOLDILOCKS": 0.16, "REFLASYON": 0.16, "STAGFLASYON": 0.14, "DEFLASYON": 0.18}, False, True), 
            ("Küresel Deniz Ticareti/Navlun (BDRY)", fetch_yf_data('BDRY'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.16, "STAGFLASYON": 0.18, "DEFLASYON": 0.06}, True, False), 
            ("10Y Breakeven Enflasyon İvmesi", fetch_fred_data('T10YIE'), {"GOLDILOCKS": 0.12, "REFLASYON": 0.14, "STAGFLASYON": 0.16, "DEFLASYON": 0.06}, True, True),
            ("G4 Küresel Süper Likidite (Fed+ECB+BoJ+Çin)", fetch_g4_global_net_liquidity(), {"GOLDILOCKS": 0.08, "REFLASYON": 0.06, "STAGFLASYON": 0.02, "DEFLASYON": 0.10}, False, False),
            ("MOVE Endeksi (Tahvil Volatilitesi)", fetch_yf_data('^MOVE'), {"GOLDILOCKS": 0.04, "REFLASYON": 0.04, "STAGFLASYON": 0.04, "DEFLASYON": 0.04}, True, False),
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
            "Reel İvme (Z-Skor)": round(z, 2),
            "Rejim Ağırlığı": f"%{dyn_weight * 100:.1f}",
            "Modele Net Katkı": round(contribution, 3)
        })

# DENGELİ VE PÜRÜZSÜZ MASTER TANH DÖNÜŞÜMÜ
raw_portfolio_score = total_score
final_trend_score = float(np.tanh(raw_portfolio_score / 0.85) * 100.0)
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
        title = {'text': f"{asset}<br>G4 Global Makro Skoru", 'font': {'size': 20}},
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
    st.markdown("### 📊 G4 Global Faktör & Navlun Tablosu")
    df_results = pd.DataFrame(indicators_data)
    st.dataframe(df_results, use_container_width=True)
    
    st.markdown("""
    **Kurumsal G4 Global Makro Rehberi:**
    * **G4 Süper Likidite Havuzu:** Fed, ECB, Bank of Japan (BoJ) ve Çin kredi/FX akımları tek bir küresel dolar likidite havuzunda toplanmıştır.
    * **Baltic Dry Navlun Endeksi (BDRY):** Küresel gemi taşımacılığı maliyetlerini ve fiziki tedarik zinciri baskısını ölçer.
    * **Tam Enerji Kompleksi & Crack Spread:** Brent/WTI makası, Rafineri Benzin/Dizel marjı ve Doğal Gaz (`NG=F`) ile küresel enerji talebi modellenmiştir.
    * **Reel İskonto Çıpası (DFII10):** Fisher denklemi üzerinden tüm varlıkların küresel sermaye maliyeti hesaplanır.
    """)
