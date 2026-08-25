import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from fredapi import Fred
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. AYARLAR VE API ---
st.set_page_config(page_title="Makro Trend v3.3", layout="wide")

try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=FRED_API_KEY)
except:
    st.error("Lütfen Streamlit Cloud ayarlarına FRED_API_KEY eklediğinizden emin olun!")
    st.stop()

# --- 2. GELİŞMİŞ VERİ ÇEKME FONKSİYONLARI ---
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

# --- 3. REJİM HESAPLAMA ---
def get_macro_regime():
    cpi = fetch_fred_data('CPIAUCSL')
    unrate = fetch_fred_data('UNRATE')
    
    if len(cpi) < 12 or len(unrate) < 3:
        return "NÖTR", 1.0 
        
    cpi_yoy = (cpi.iloc[-1] - cpi.iloc[-12]) / cpi.iloc[-12] * 100
    cpi_yoy_prev = (cpi.iloc[-2] - cpi.iloc[-13]) / cpi.iloc[-13] * 100
    inflation_rising = cpi_yoy > cpi_yoy_prev
    
    unrate_rising = unrate.iloc[-1] > unrate.iloc[-3]
    
    if not inflation_rising and not unrate_rising:
        return "GOLDILOCKS (Düşen Enflasyon, Güçlü Büyüme)", 1.2
    elif inflation_rising and not unrate_rising:
        return "REFLASYON (Artan Enflasyon, Güçlü Büyüme)", 1.1
    elif inflation_rising and unrate_rising:
        return "STAGFLASYON (Artan Enflasyon, Zayıf Büyüme)", 1.5
    else:
        return "DEFLASYON (Düşen Enflasyon, Zayıf Büyüme)", 1.3

# --- 4. Z-SKOR MOTORU (FAİZ DEĞİŞİM - BAZ PUAN MANTIĞI EKLENDİ) ---
def process_indicator(data_series, invert=False, is_rate=False):
    if isinstance(data_series, pd.DataFrame):
        data_series = data_series.iloc[:, 0]
        
    data_series = data_series.dropna()
    
    if len(data_series) < 200:
        val = float(data_series.iloc[-1]) if not data_series.empty else 0.0
        return 0.0, val
    
    # EĞER VERİ BİR FAİZ/SPREAD İSE YALIN DEĞER YERİNE 60 GÜNLÜK BAZ PUAN İVMESİ BAZ ALINIR
    if is_rate:
        # Son 60 günlük baz puan değişimi (momentum)
        momentum = data_series.diff(60).dropna()
        if len(momentum) < 200:
            return 0.0, float(data_series.iloc[-1])
        
        ema_60 = momentum.ewm(span=60, adjust=False).mean()
    else:
        # Normal Fiyat/Endeks Verisi İse Normal 60 Günlük EMA
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
    
    # Ekranda gösterilecek ham değer
    display_val = float(data_series.iloc[-1])
    return z_score, display_val

# --- 5. ARAYÜZ VE UYGULAMA MANTIĞI ---
st.title("🏛️ KÜRESEL MAKRO & SWING TREND MODELİ (v3.3)")
st.markdown("**Tam Kapsamlı Kurumsal Rejim, Bps İvmesi ve Z-Skor Motoru**")

st.sidebar.header("VARLIK SEÇİMİ")
asset = st.sidebar.radio("Analiz Edilecek Varlığı Seçin:", ("Altın (XAU)", "Gümüş (XAG)", "Nasdaq 100 (NQ)", "S&P 500 (SPX)"))

regime_name, regime_multiplier = get_macro_regime()
st.subheader(f"Mevcut Makro Rejim: **{regime_name}**")

indicators_data = []
total_score = 0

with st.spinner(f"{asset} için 10 ayrı kurumsal katman ve faiz ivmeleri (bps) hesaplanıyor..."):
    # (Gösterge Adı, Data, Ağırlık, TersMi, FaizMi)
    if asset == "Altın (XAU)":
        metrics = [
            ("Reel Faiz Momentum (10Y TIPS)", fetch_fred_data('DFII10'), 0.15, True, True), # is_rate=True
            ("MOVE Endeksi (Tahvil Paniği)", fetch_yf_data('^MOVE'), 0.12, False, False), 
            ("Kurumsal Kredi Stresi (OAS)", fetch_fred_data('BAMLC0A0CM'), 0.10, False, True), # is_rate=True
            ("Fed Net Likiditesi (Bilanço)", fetch_fred_data('WALCL'), 0.10, False, False),
            ("Getiri Eğrisi Eğim İvmesi (10Y-2Y)", fetch_fred_data('T10Y2Y'), 0.10, False, True), # HATA DÜZELTİLDİ, is_rate=True
            ("Dolar Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.10, True, False), 
            ("Altın / Petrol Stagflasyon Rasyosu", fetch_yf_data('GC=F') / fetch_yf_data('CL=F'), 0.08, False, False),
            ("S&P 500 / Altın Rasyosu (Fırsat Maliyeti)", fetch_yf_data('^GSPC') / fetch_yf_data('GC=F'), 0.10, True, False), 
            ("Altın Momentum Trendi (GC=F)", fetch_yf_data('GC=F'), 0.08, False, False),
            ("Bakır / Altın Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.07, True, False), 
        ]
    elif asset == "Gümüş (XAG)":
        metrics = [
            ("Endüstriyel Metaller Sepeti (DBB)", fetch_yf_data('DBB'), 0.15, False, False),
            ("Gümüş Momentum Trendi (SI=F)", fetch_yf_data('SI=F'), 0.15, False, False),
            ("Bakır / Altın Büyüme Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.12, False, False),
            ("Kurumsal Kredi Stresi (OAS)", fetch_fred_data('BAMLC0A0CM'), 0.10, True, True), # is_rate=True
            ("Dolar Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.10, True, False), 
            ("Altın / Gümüş Ayrışma (Divergence) Rasyosu", fetch_yf_data('GC=F') / fetch_yf_data('SI=F'), 0.10, True, False), 
            ("Çin Piyasası İvmesi (MCHI)", fetch_yf_data('MCHI'), 0.08, False, False), 
            ("ABD 10Y Tahvil Faizi", fetch_yf_data('^TNX'), 0.08, True, True), # is_rate=True
            ("S&P 500 Risk İştahı", fetch_yf_data('^GSPC'), 0.07, False, False),
            ("Ham Petrol Sanayi Talebi (WTI)", fetch_yf_data('CL=F'), 0.05, False, False),
        ]
    elif asset == "Nasdaq 100 (NQ)":
        metrics = [
            ("Ticari Banka Rezervleri (Direkt Yakıt)", fetch_fred_data('WRESBAL'), 0.15, False, False),
            ("NQ / 10Y Risk Primi Proxy", fetch_yf_data('QQQ') / fetch_yf_data('^TNX'), 0.12, False, False),
            ("Yen Carry Trade Döngüsü (USD/JPY)", fetch_yf_data('JPY=X'), 0.12, False, False), 
            ("VIX Volatilite Eğilimi", fetch_yf_data('^VIX'), 0.10, True, False), 
            ("Yarı İletken Liderliği (SOXX/QQQ)", fetch_yf_data('SOXX') / fetch_yf_data('QQQ'), 0.10, False, False),
            ("Kurumsal Kredi Stresi (OAS)", fetch_fred_data('BAMLC0A0CM'), 0.10, True, True), 
            ("MOVE Endeksi (Tahvil Baskısı)", fetch_yf_data('^MOVE'), 0.10, True, False), 
            ("Fed Toplam Bilanço Genişlemesi", fetch_fred_data('WALCL'), 0.08, False, False),
            ("SKEW Siyah Kuğu Kuyruk Riski", fetch_yf_data('^SKEW'), 0.08, True, False), 
            ("Dolar Endeksi (DX-Y.NYB)", fetch_yf_data('DX-Y.NYB'), 0.05, True, False), 
        ]
    else:
        # YENİ EKLENEN S&P 500 (SPX) MODELİ
        metrics = [
            ("Ticari Banka Rezervleri (Likidite)", fetch_fred_data('WRESBAL'), 0.15, False, False),
            ("Eşit Ağırlık Piyasa Genişliği (RSP/SPY)", fetch_yf_data('RSP') / fetch_yf_data('SPY'), 0.12, False, False), # Piyasa sağlığı
            ("Kurumsal Kredi Stresi (OAS)", fetch_fred_data('BAMLC0A0CM'), 0.12, True, True), # is_rate=True
            ("Reel Faiz Bps İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), 0.10, True, True), # is_rate=True
            ("MOVE Endeksi (Tahvil Volatilitesi)", fetch_yf_data('^MOVE'), 0.10, True, False),
            ("VIX Volatilite Eğilimi", fetch_yf_data('^VIX'), 0.10, True, False),
            ("Bakır / Altın Rasyosu (Global Büyüme)", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.08, False, False),
            ("SKEW Siyah Kuğu Riski", fetch_yf_data('^SKEW'), 0.08, True, False),
            ("Yen Carry Trade (USD/JPY)", fetch_yf_data('JPY=X'), 0.08, False, False),
            ("Dolar Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.07, True, False),
        ]

    for name, data_series, weight, invert, is_rate in metrics:
        z, val = process_indicator(data_series, invert, is_rate)
        contribution = z * weight * regime_multiplier
        total_score += contribution
        
        # Faiz/Getiri oranları için ekran çıktısını % formatına dönüştür
        if val == 0:
            display_str = "Hesaplanıyor / Veri Yok"
        elif is_rate:
            display_str = f"%{val:.2f}"
        else:
            display_str = f"{val:.4f}"
            
        indicators_data.append({
            "Makro Gösterge (Katman)": name,
            "Güncel Değer (Fiyat / Seviye)": display_str,
            "1-Yıllık İvme Skoru (-3 / +3)": round(z, 2),
            "Etki Ağırlığı": weight,
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
        title = {'text': f"{asset}<br>Makro Trend Skoru", 'font': {'size': 20}},
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
    st.markdown("### 📊 10 Katmanlı Analiz & Skor Dağılımı")
    df_results = pd.DataFrame(indicators_data)
    st.dataframe(df_results, use_container_width=True)
    
    st.markdown("""
    **Kurumsal Skor Rehberi:**
    * **+60 ile +100 : Güçlü Boğa Trendi** (Makro şartlar kusursuz, alıcı hakimiyeti)
    * **+20 ile +60 : Zayıf Boğa Trendi** (Eğilim yukarı ancak bazı makro riskler var)
    * **-20 ile +20 : Nötr / Konsolidasyon** (Belirgin bir makro trend yok, yatay piyasa)
    * **-20 ile -60 : Zayıf Ayı Trendi** (Eğilim aşağı, temeller zayıf, fiyat düzeltmesi riski)
    * **-60 ile -100 : Güçlü Ayı Trendi** (Makro şartlar tamamen olumsuz, sert düşüş riski)
    
    *(Not: Reel faiz ve spread gibi metriklerin Z-skorları; mevcut yüzde seviyelerinden değil, son 60 günlük baz puan ivmelenmelerinden (momentum) hesaplanarak risk skalasına dönüştürülür).*
    """)
