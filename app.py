import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from fredapi import Fred
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. AYARLAR VE API ---
st.set_page_config(page_title="Makro Trend v3.0", layout="wide")

# FRED API Anahtarını Streamlit Secrets'tan al
try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=FRED_API_KEY)
except:
    st.error("Lütfen Streamlit Cloud ayarlarına FRED_API_KEY eklediğinizden emin olun!")
    st.stop()

# --- 2. VERİ ÇEKME FONKSİYONLARI ---
@st.cache_data(ttl=3600) # Verileri 1 saat önbellekte tut
def fetch_fred_data(series_id, days=1000):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    try:
        data = fred.get_series(series_id, start_date, end_date)
        return data.ffill().dropna()
    except:
        return pd.Series(dtype=float)

@st.cache_data(ttl=3600)
def fetch_yf_data(ticker, days=1000):
    try:
        data = yf.download(ticker, period=f"{days}d", progress=False)
        # Yahoo verisi tablo gelirse sadece Kapanış (Close) sütununu al
        if 'Close' in data.columns:
            close_data = data['Close']
        else:
            close_data = data.iloc[:, 0]
            
        if isinstance(close_data, pd.DataFrame):
            close_data = close_data.iloc[:, 0]
            
        return close_data.ffill().dropna()
    except:
        return pd.Series(dtype=float)

# --- 3. REJİM HESAPLAMA (Enflasyon & Büyüme) ---
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

# --- 4. Z-SKOR VE GÖSTERGE MOTORU (HATA DÜZELTİLDİ) ---
def process_indicator(data_series, invert=False):
    # Eğer gelen veri DataFrame (Tablo) formatındaysa tek bir seriye (sütuna) dönüştür
    if isinstance(data_series, pd.DataFrame):
        data_series = data_series.iloc[:, 0]
        
    data_series = data_series.dropna()
    
    if len(data_series) < 200:
        val = float(data_series.iloc[-1]) if not data_series.empty else 0.0
        return 0.0, val
    
    # 60 Günlük EMA
    ema_60 = data_series.ewm(span=60, adjust=False).mean()
    
    # 1 Yıllık Z-Skor
    mean_252 = ema_60.rolling(window=252).mean()
    std_252 = ema_60.rolling(window=252).std()
    
    # KESİN ÇÖZÜM: Değerleri zorla float (tekil sayı) formatına çeviriyoruz
    current_val = float(ema_60.iloc[-1])
    mean_val = float(mean_252.iloc[-1])
    std_val = float(std_252.iloc[-1])
    
    z_score = (current_val - mean_val) / (std_val + 1e-5)
    
    if invert:
        z_score = -z_score
        
    # Artık z_score %100 bir sayı olduğu için min/max fonksiyonu çökmeyecek
    z_score = float(max(-3.0, min(3.0, z_score)))
    
    return z_score, float(data_series.iloc[-1])

# --- 5. ARAYÜZ VE UYGULAMA MANTIĞI ---
st.title("🏛️ KÜRESEL MAKRO & SWING TREND MODELİ (v3.0)")
st.markdown("**Kurumsal Likidite, Oynaklık ve Rejim Filtreli Z-Skor Motoru**")

st.sidebar.header("VARLIK SEÇİMİ")
asset = st.sidebar.radio("Analiz Edilecek Varlığı Seçin:", ("Altın (XAU)", "Gümüş (XAG)", "Nasdaq 100 (NQ)"))
st.sidebar.markdown("---")
st.sidebar.info("Model verileri FRED ve Yahoo Finance API'lerinden canlı çekerek 60 günlük EMA ve Z-Skor üzerinden rejim analizi yapar.")

regime_name, regime_multiplier = get_macro_regime()
st.subheader(f"Mevcut Makro Rejim: **{regime_name}**")

indicators_data = []
total_score = 0

with st.spinner(f"{asset} için küresel kurumsal veriler çekiliyor..."):
    if asset == "Altın (XAU)":
        metrics = [
            ("Reel Faiz İvmesi (10Y TIPS)", fetch_fred_data('DFII10'), 0.15, True),
            ("MOVE Endeksi (Tahvil Paniği)", fetch_yf_data('^MOVE'), 0.12, False),
            ("Bilanço & Likidite (Fed)", fetch_fred_data('WALCL'), 0.10, False),
            ("Getiri Eğrisi (10Y-2Y)", fetch_fred_data('T10Y22Y'), 0.10, False),
            ("Dolar Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.08, True),
        ]
    elif asset == "Gümüş (XAG)":
        metrics = [
            ("Endüstriyel Metaller (DBB)", fetch_yf_data('DBB'), 0.15, False),
            ("Gümüş Kapanış Trendi", fetch_yf_data('SI=F'), 0.15, False),
            ("Bakır/Altın Rasyosu", fetch_yf_data('HG=F') / fetch_yf_data('GC=F'), 0.12, False),
            ("Kredi Spread Risk (HYG/TLT)", fetch_yf_data('HYG') / fetch_yf_data('TLT'), 0.10, False),
            ("Dolar Eğilimi (DXY)", fetch_yf_data('DX-Y.NYB'), 0.08, True),
        ]
    else:
        metrics = [
            ("Banka Rezervleri (Likidite)", fetch_fred_data('WRESBAL'), 0.15, False),
            ("VIX Volatilite Endeksi", fetch_yf_data('^VIX'), 0.12, True),
            ("Yen Carry Trade (USD/JPY)", fetch_yf_data('JPY=X'), 0.10, False),
            ("Kredi Spread Stresi (HYG/TLT)", fetch_yf_data('HYG') / fetch_yf_data('TLT'), 0.10, False),
            ("Yarı İletken Gücü (SOXX/QQQ)", fetch_yf_data('SOXX') / fetch_yf_data('QQQ'), 0.08, False),
        ]

    for name, data_series, weight, invert in metrics:
        z, val = process_indicator(data_series, invert)
        contribution = z * weight * regime_multiplier
        total_score += contribution
        
        indicators_data.append({
            "Makro Gösterge": name,
            "Güncel Değer": round(val, 4) if val != 0 else "Veri Yok",
            "Z-Skor": round(z, 2),
            "Ağırlık": weight,
            "Trend Katkısı": round(contribution, 3)
        })

final_trend_score = max(-100, min(100, total_score * 25))

# --- 6. GÖRSELLEŞTİRME VE SONUÇ ---
col1, col2 = st.columns([1, 1])

with col1:
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = final_trend_score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"{asset}<br>Kurumsal Makro Trend Skoru", 'font': {'size': 20}},
        gauge = {
            'axis': {'range': [-100, 100], 'tickwidth': 1},
            'bar': {'color': "black"},
            'steps': [
                {'range': [-100, -60], 'color': "#ff4b4b"},  # Güçlü Ayı
                {'range': [-60, -20], 'color': "#ffa07a"},  # Zayıf Ayı
                {'range': [-20, 20], 'color': "#f0e68c"},   # Nötr
                {'range': [20, 60], 'color': "#90ee90"},    # Zayıf Boğa
                {'range': [60, 100], 'color': "#32cd32"}    # Güçlü Boğa
            ],
        }
    ))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.markdown("### 📊 Katman Analizi & Skor Dağılımı")
    df_results = pd.DataFrame(indicators_data)
    st.dataframe(df_results, use_container_width=True)
    
    st.markdown("""
    **Rehber:**
    * **+60 / +100 :** Güçlü Kurumsal Boğa Trendi
    * **-20 / +20 :** Nötr / Konsolidasyon
    * **-60 / -100 :** Güçlü Kurumsal Ayı Trendi
    """)
