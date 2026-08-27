import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from fredapi import Fred
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. AYARLAR VE API ---
st.set_page_config(page_title="Makro Trend v5.0 (Dynamic Fed Grade)", layout="wide")

try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=FRED_API_KEY)
except:
    st.error("Lütfen Streamlit Cloud ayarlarına FRED_API_KEY eklediğinizden emin olun!")
    st.stop()

# --- 2. GELİŞMİŞ MERKEZ BANKASI VERİ MOTORU ---
@st.cache_data(ttl=3600)
def fetch_fred_data(series_id, days=2500):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    try:
        data = fred.get_series(series_id, start_date, end_date)
        data.index = pd.to_datetime(data.index)
        return data.resample('B').ffill().dropna()
    except:
        return pd.Series(dtype=float)

@st.cache_data(ttl=3600)
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

# FED GERÇEK NET LİKİDİTE MOTORU: WALCL - TGA - RRP (Milyon Dolar Cinsinden)
@st.cache_data(ttl=3600)
def fetch_true_net_liquidity(days=2500):
    try:
        walcl = fetch_fred_data('WALCL', days)       # Fed Bilançosu (Milyon $)
        tga = fetch_fred_data('WTREGEN', days)       # Hazine Hesabı (Milyon $)
        rrp = fetch_fred_data('RRPONTSYD', days)     # Ters Repo (Milyar $) -> Milyon'a çevrilir
        
        df = pd.DataFrame({'w': walcl, 't': tga, 'r': rrp * 1000}).dropna()
        net_liq = df['w'] - df['t'] - df['r']
        return net_liq.resample('B').ffill().dropna()
    except:
        return fetch_fred_data('WALCL', days)

# --- 3. REJİM HESAPLAMA & DİNAMİK AĞIRLIK MATRİSİ ---
def get_macro_regime():
    core_pce = fetch_fred_data('PCEPILFE') 
    fwd_inf = fetch_fred_data('T5YIFR')    
    unrate = fetch_fred_data('UNRATE')     
    consumer_expectations = fetch_fred_data('UMCSENT') 
    
    if len(core_pce) < 252 or len(unrate) < 60:
        return "NOTR", "NÖTR PİYASA", 1.0 
        
    pce_yoy = (core_pce.iloc[-1] - core_pce.iloc[-252]) / core_pce.iloc[-252] * 100
    pce_yoy_prev = (core_pce.iloc[-22] - core_pce.iloc[-274]) / core_pce.iloc[-274] * 100
    pce_rising = pce_yoy > pce_yoy_prev
    
    fwd_rising = fwd_inf.iloc[-1] > fwd_inf.iloc[-60] if len(fwd_inf) > 60 else False
    unrate_rising = unrate.iloc[-1] > unrate.iloc[-60]

    future_optimism = False
    if len(consumer_expectations) > 60:
        future_optimism = consumer_expectations.iloc[-1] > consumer_expectations.iloc[-60]
    
    inflation_pressure = pce_rising or fwd_rising
    
    if not inflation_pressure and not unrate_rising:
        mult = 1.3 if future_optimism else 1.2
        return "GOLDILOCKS", "GOLDILOCKS (Düşen Enflasyon, Güçlü Büyüme)", mult
    elif inflation_pressure and not unrate_rising:
        mult = 1.2 if future_optimism else 1.1
        return "REFLASYON", "REFLASYON (Artan Enflasyon Baskısı, Güçlü Büyüme)", mult
    elif inflation_pressure and unrate_rising:
        mult = 1.4 if not future_optimism else 1.5 
        return "STAGFLASYON", "STAGFLASYON (Artan Enflasyon, Zayıflayan İstihdam)", mult
    else:
        mult = 1.4 if not future_optimism else 1.3
        return "DEFLASYON", "DEFLASYONİST DARALMA (Düşen Enflasyon, Zayıf Büyüme)", mult

# Rejimlere göre Kategori Ağırlık Katsayıları (Regime Multiplier Matrix)
REGIME_CATEGORY_WEIGHTS = {
    "GOLDILOCKS": {
        "LIKIDITE": 1.4,
        "BUYUME_SANAYI": 1.4,
        "FAIZ_BEKLENTI": 1.1,
        "ENFLASYON": 0.6,
        "RISK_STRES": 0.6
    },
    "REFLASYON": {
        "LIKIDITE": 1.2,
        "BUYUME_SANAYI": 1.3,
        "ENFLASYON": 1.3,
        "FAIZ_BEKLENTI": 1.0,
        "RISK_STRES": 0.7
    },
    "STAGFLASYON": {
        "ENFLASYON": 1.7,
        "RISK_STRES": 1.5,
        "FAIZ_BEKLENTI": 1.2,
        "LIKIDITE": 0.7,
        "BUYUME_SANAYI": 0.5
    },
    "DEFLASYON": {
        "RISK_STRES": 1.6,
        "FAIZ_BEKLENTI": 1.4,
        "LIKIDITE": 1.2,
        "BUYUME_SANAYI": 0.5,
        "ENFLASYON": 0.5
    },
    "NOTR": {
        "LIKIDITE": 1.0,
        "BUYUME_SANAYI": 1.0,
        "FAIZ_BEKLENTI": 1.0,
        "ENFLASYON": 1.0,
        "RISK_STRES": 1.0
    }
}

# --- 4. Z-SKOR MOTORU ---
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
        ema_60 = momentum.ewm(span=60, adjust=False).mean()
    else:
        ema_60 = data_series.ewm(span=60, adjust=False).mean()
        
    mean_252 = ema_60.rolling(window=252).mean()
    std_252 = ema_60.rolling(window=252).std()
    
    current_val = float(ema_60.iloc[-1])
    mean_val = float(mean_252.iloc[-1])
    std_val = float(std_252.iloc[-1])
    
    z_score = (current_val - mean_val) / (std_val + 1e-5)
    
    if invert:
        z_score = -z_score
        
    z_score = float(max(-3.0, min(3.0, z_score)))
    display_val = float(data_series.iloc[-1])
    return z_score, display_val

# --- 5. ARAYÜZ VE UYGULAMA MANTIĞI ---
st.title("🏛️ KÜRESEL MAKRO & SWING TREND MODELİ (v5.0 - DYNAMIC REGIME)")
st.markdown("**Tam Dinamik Rejim Ağırlıklandırması (Dynamic Regime-Switching) & Likidite Motoru**")

st.sidebar.header("VARLIK SEÇİMİ")
asset = st.sidebar.radio("Analiz Edilecek Varlığı Seçin:", ("Altın (XAU)", "Gümüş (XAG)", "Nasdaq 100 (NQ)", "S&P 500 (SPX)"))

regime_code, regime_name, regime_multiplier = get_macro_regime()
st.subheader(f"Mevcut Makro Rejim: **{regime_name}**")

indicators_data = []
total_score = 0

with st.spinner(f"{asset} için Dinamik Rejim Matrisi ve Göstergeler taranıyor..."):
    # Format: (Gösterge Adı, Data, Taban Ağırlık, Kategori, TersMi, FaizMi)
    if asset == "Altın (XAU)":
        metrics = [
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), 0.12, "FAIZ_BEKLENTI", True, True),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.10, "FAIZ_BEKLENTI", True, True),
            ("5y5y Forward Enflasyon Çıpası (T5YIFR)", fetch_fred_data('T5YIFR'), 0.10, "ENFLASYON", False, True),
            ("Fed Gerçek Net Dolar Likiditesi", fetch_true_net_liquidity(), 0.10, "LIKIDITE", False, False),
            ("Likidite Gelecek İvmesi (30G Hız)", fetch_true_net_liquidity().diff(20), 0.06, "LIKIDITE", False, False),
            ("MOVE Endeksi (Tahvil Paniği)", fetch_yf_data('^MOVE'), 0.09, "RISK_STRES", False, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.09, "RISK_STRES", False, False),
            ("Getiri Eğrisi Eğim İvmesi (10Y-2Y)", fetch_fred_data('T10Y2Y'), 0.09, "FAIZ_BEKLENTI", False, True),
            ("Kurumsal Kredi Stresi (OAS Spread)", fetch_fred_data('BAMLC0A0CM'), 0.08, "RISK_STRES", False, True),
            ("Dolar Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.08, "LIKIDITE", True, False),
            ("Altın / Petrol Stagflasyon Rasyosu", fetch_yf_data('GC=F') / fetch_yf_data('CL=F'), 0.05, "ENFLASYON", False, False),
            ("Bakır / Altın Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.04, "BUYUME_SANAYI", True, False),
        ]
    elif asset == "Gümüş (XAG)":
        metrics = [
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), 0.12, "BUYUME_SANAYI", False, False),
            ("Gümüş Momentum Trendi (SI=F)", fetch_yf_data('SI=F'), 0.12, "BUYUME_SANAYI", False, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.10, "FAIZ_BEKLENTI", True, True),
            ("5y5y Forward Enflasyon Çıpası (T5YIFR)", fetch_fred_data('T5YIFR'), 0.10, "ENFLASYON", False, True),
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.10, "BUYUME_SANAYI", False, False),
            ("Fed Gerçek Net Dolar Likiditesi", fetch_true_net_liquidity(), 0.08, "LIKIDITE", False, False),
            ("Likidite Gelecek İvmesi (30G Hız)", fetch_true_net_liquidity().diff(20), 0.05, "LIKIDITE", False, False),
            ("Altın / Gümüş Ayrışma Rasyosu", fetch_yf_data('GC=F') / fetch_yf_data('SI=F'), 0.08, "BUYUME_SANAYI", True, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.08, "RISK_STRES", True, False),
            ("Çin Piyasası İvmesi (MCHI)", fetch_yf_data('MCHI'), 0.07, "BUYUME_SANAYI", False, False),
            ("Kurumsal Kredi Stresi (OAS)", fetch_fred_data('BAMLC0A0CM'), 0.05, "RISK_STRES", True, True),
            ("Dolar Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.05, "LIKIDITE", True, False),
        ]
    elif asset == "Nasdaq 100 (NQ)":
        metrics = [
            ("Fed Gerçek Net Dolar Likiditesi", fetch_true_net_liquidity(), 0.12, "LIKIDITE", False, False),
            ("Likidite Gelecek İvmesi (30G Hız)", fetch_true_net_liquidity().diff(20), 0.08, "LIKIDITE", False, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.12, "RISK_STRES", True, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.10, "FAIZ_BEKLENTI", True, True),
            ("Ticari Banka Rezervleri (WRESBAL)", fetch_fred_data('WRESBAL'), 0.10, "LIKIDITE", False, False),
            ("NQ / 10Y Risk Primi Proxy", fetch_yf_data('QQQ') / fetch_yf_data('^TNX'), 0.08, "BUYUME_SANAYI", False, False),
            ("Yen Carry Trade Döngüsü (USD/JPY)", fetch_yf_data('JPY=X'), 0.08, "LIKIDITE", False, False),
            ("VIX Volatilite Eğilimi", fetch_yf_data('^VIX'), 0.08, "RISK_STRES", True, False),
            ("Yarı İletken Liderliği (SOXX/QQQ)", fetch_yf_data('SOXX') / fetch_yf_data('QQQ'), 0.08, "BUYUME_SANAYI", False, False),
            ("MOVE Endeksi (Tahvil Baskısı)", fetch_yf_data('^MOVE'), 0.06, "RISK_STRES", True, False),
            ("Kurumsal Kredi Stresi (OAS)", fetch_fred_data('BAMLC0A0CM'), 0.05, "RISK_STRES", True, True),
            ("SKEW Siyah Kuğu Kuyruk Riski", fetch_yf_data('^SKEW'), 0.05, "RISK_STRES", True, False),
        ]
    else:
        # S&P 500 (SPX) MODELİ
        metrics = [
            ("Fed Gerçek Net Dolar Likiditesi", fetch_true_net_liquidity(), 0.12, "LIKIDITE", False, False),
            ("Likidite Gelecek İvmesi (30G Hız)", fetch_true_net_liquidity().diff(20), 0.08, "LIKIDITE", False, False),
            ("Chicago Fed Finansal Koşullar (NFCI)", fetch_fred_data('NFCI'), 0.12, "RISK_STRES", True, False),
            ("Piyasa Faiz İndirim Beklentisi (2Y)", fetch_fred_data('DGS2'), 0.10, "FAIZ_BEKLENTI", True, True),
            ("Ticari Banka Rezervleri (WRESBAL)", fetch_fred_data('WRESBAL'), 0.10, "LIKIDITE", False, False),
            ("Eşit Ağırlık Piyasa Genişliği (RSP/SPY)", fetch_yf_data('RSP') / fetch_yf_data('SPY'), 0.09, "BUYUME_SANAYI", False, False),
            ("Kurumsal Kredi Stresi (OAS)", fetch_fred_data('BAMLC0A0CM'), 0.08, "RISK_STRES", True, True),
            ("5y5y Forward Enflasyon Çıpası (T5YIFR)", fetch_fred_data('T5YIFR'), 0.08, "ENFLASYON", True, True),
            ("VIX Volatilite Eğilimi", fetch_yf_data('^VIX'), 0.08, "RISK_STRES", True, False),
            ("MOVE Endeksi (Tahvil Volatilitesi)", fetch_yf_data('^MOVE'), 0.06, "RISK_STRES", True, False),
            ("Bakır / Altın Rasyosu (Global Büyüme)", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.05, "BUYUME_SANAYI", False, False),
            ("Yen Carry Trade (USD/JPY)", fetch_yf_data('JPY=X'), 0.04, "LIKIDITE", False, False),
        ]

    # --- TAM DİNAMİK AĞIRLIK HESAPLAMA MOTORU ---
    # 1. Aşama: Rejim katsayılarını uygula
    raw_dynamic_weights = []
    regime_multipliers_dict = REGIME_CATEGORY_WEIGHTS.get(regime_code, REGIME_CATEGORY_WEIGHTS["NOTR"])
    
    for item in metrics:
        base_w = item[2]
        cat = item[3]
        cat_mult = regime_multipliers_dict.get(cat, 1.0)
        raw_dynamic_weights.append(base_w * cat_mult)
        
    # 2. Aşama: Toplamı tam 1.00 (%100) olacak şekilde normalize et
    total_raw_weight = sum(raw_dynamic_weights)
    dynamic_weights = [w / total_raw_weight for w in raw_dynamic_weights]

    # 3. Aşama: Z-skorlarını dinamik ağırlıklarla çarp ve skoru topla
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
        else:
            display_str = f"{val:.2f}" if abs(val) < 1000 else f"{val:,.0f}"
            
        indicators_data.append({
            "Makro Gösterge (Katman)": name,
            "Kategori": category,
            "Güncel Değer": display_str,
            "1-Yıllık İvme Skoru (-3 / +3)": round(z, 2),
            "Dinamik Ağırlık": f"%{dyn_weight * 100:.1f}",
            "Modele Net Katkısı": round(contribution, 3)
        })

# Normalizasyon ve Grafik
final_trend_score = max(-100, min(100, total_score * 25))

col1, col2 = st.columns([1, 1.2])

with col1:
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = final_trend_score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"{asset}<br>Dinamik Fed-Grade Skoru", 'font': {'size': 20}},
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

with col2:
    st.markdown("### 📊 Dinamik Katman Analizi & Skor Dağılımı")
    df_results = pd.DataFrame(indicators_data)
    st.dataframe(df_results, use_container_width=True)
    
    st.markdown("""
    **Kurumsal Skor Rehberi:**
    * **+60 ile +100 : Güçlü Boğa Trendi** (Likidite ve makro şartlar tam uyumlu, alıcı hakimiyeti)
    * **+20 ile +60 : Zayıf Boğa Trendi** (Eğilim yukarı ancak bazı finansal sıkılık riskleri var)
    * **-20 ile +20 : Nötr / Konsolidasyon** (Belirgin bir yön rüzgarı yok, yatay piyasa)
    * **-20 ile -60 : Zayıf Ayı Trendi** (Likidite çekiliyor, fiyat düzeltmesi riski)
    * **-60 ile -100 : Güçlü Ayı Trendi** (Makro şartlar tamamen olumsuz, sert düşüş riski)
    
    *(Not: Model; Aktif Makro Rejime göre göstergelerin ağırlıklarını anlık olarak **Regime-Switching** matrisiyle yeniden dağıtır, toplam ağırlık her zaman %100'e normalize edilir).*
    """)
