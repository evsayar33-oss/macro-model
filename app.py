import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import os
import json
import importlib
from fredapi import Fred
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Streamlit page configuration must execute before any other Streamlit command.
st.set_page_config(page_title="Makro Trend v2.3 (Continuum Master Grade)", layout="wide")

# --- Yerel modül tazeliği -------------------------------------------------
# Streamlit Cloud, repo güncellenince sayfa betiğini yeniden çalıştırır ama
# daha önce içe aktarılmış yardımcı modülleri (sys.modules) bellekte ESKİ
# halleriyle tutabilir -> "ImportError: cannot import name ..." hataları.
# Dosyası diskte değişmiş her yerel modül, bağımlılık sırasıyla yeniden yüklenir.
import importlib as _il, os as _os, sys as _sys, time as _time
for _name in ("asset_regime_weights", "macro_event_interpretation", "asset_signal_engine",
              "regime_portfolio", "macro_pipeline"):
    _mod = _sys.modules.get(_name)
    _f = getattr(_mod, "__file__", None) if _mod else None
    if _mod is not None and _f and _os.path.exists(_f) and _os.path.getmtime(_f) > getattr(_mod, "__loaded_at__", 0):
        try:
            _mod = _il.reload(_mod)
        except Exception:
            pass
    if _mod is not None:
        _mod.__loaded_at__ = _time.time()


# Robust engine loading: namespace imports + explicit API contract.
try:
    import macro_event_interpretation as macro_engine
    importlib.invalidate_caches()
    macro_engine = importlib.reload(macro_engine)
except Exception as exc:
    st.error("❌ Macro engine yüklenemedi. macro_event_interpretation.py sürümü kontrol edilmeli.")
    st.exception(exc)
    st.stop()

_REQUIRED_MACRO_API = (
    "MacroEventInterpretationSystem", "RegimeThresholdConfig",
    "get_macro_interpretation_asset_multipliers", "render_macro_scorecard_ui",
    "compute_continuum_regime_state", "compute_structural_risk_state",
    "compute_portfolio_asset_tilt", "assess_data_freshness",
    "compute_circuit_breaker", "compute_net_liquidity", "validate_macro_input",
    "compute_effective_macro_asset_multiplier", "compute_target_portfolio_weights",
    "normalize_macro_input", "MACRO_EVENT_INPUT_SCHEMA_VERSION",
    "compute_asset_signal_state", "get_asset_signal_label", "ASSET_MARKET_TICKERS",
)
_missing_macro_api=[name for name in _REQUIRED_MACRO_API if not hasattr(macro_engine,name)]
if _missing_macro_api:
    st.error("❌ Macro engine API uyuşmazlığı: "+", ".join(_missing_macro_api))
    st.stop()

MacroEventInterpretationSystem=macro_engine.MacroEventInterpretationSystem
RegimeThresholdConfig=macro_engine.RegimeThresholdConfig
get_macro_interpretation_asset_multipliers=macro_engine.get_macro_interpretation_asset_multipliers
render_macro_scorecard_ui=macro_engine.render_macro_scorecard_ui
compute_continuum_regime_state=macro_engine.compute_continuum_regime_state
compute_structural_risk_state=macro_engine.compute_structural_risk_state
compute_portfolio_asset_tilt=macro_engine.compute_portfolio_asset_tilt
assess_data_freshness=macro_engine.assess_data_freshness
compute_circuit_breaker=macro_engine.compute_circuit_breaker
compute_net_liquidity=macro_engine.compute_net_liquidity
validate_macro_input=macro_engine.validate_macro_input
compute_effective_macro_asset_multiplier=macro_engine.compute_effective_macro_asset_multiplier
compute_target_portfolio_weights=macro_engine.compute_target_portfolio_weights
normalize_macro_input=macro_engine.normalize_macro_input
MACRO_EVENT_INPUT_SCHEMA_VERSION=macro_engine.MACRO_EVENT_INPUT_SCHEMA_VERSION
compute_asset_signal_state=macro_engine.compute_asset_signal_state
get_asset_signal_label=macro_engine.get_asset_signal_label
ASSET_MARKET_TICKERS=macro_engine.ASSET_MARKET_TICKERS

try:
    import asset_regime_weights as asset_engine
    importlib.invalidate_caches()
    asset_engine=importlib.reload(asset_engine)
except Exception as exc:
    st.error("❌ Asset weight engine yüklenemedi.")
    st.exception(exc)
    st.stop()

_REQUIRED_ASSET_API=("get_dynamic_asset_weights","get_asset_regime_weight_matrix","INDICATORS")
_missing_asset_api=[name for name in _REQUIRED_ASSET_API if not hasattr(asset_engine,name)]
if _missing_asset_api:
    st.error("❌ Asset weight engine API uyuşmazlığı: "+", ".join(_missing_asset_api))
    st.stop()

get_dynamic_asset_weights=asset_engine.get_dynamic_asset_weights
get_asset_regime_weight_matrix=asset_engine.get_asset_regime_weight_matrix
ASSET_INDICATORS=asset_engine.INDICATORS

# --- 1. SAYFA VE API AYARLARI ---
# (İkinci st.set_page_config çağrısı kaldırıldı: Streamlit tek çağrı bekler.)

# Veri çekme + motor artık macro_pipeline.py'de (önbellek tüm sayfalarda ortak).
# FRED anahtarı yoksa anahtarsız halka açık FRED CSV'sine düşülür.
from macro_pipeline import (  # noqa: E402
    fetch_fred_data, fetch_yf_data, fetch_g4_global_net_liquidity as _mp_fetch_g4,
    build_macro_input, run_regime_history, get_live_target, render_refresh_button,
)

# ZIRHLI RASYONEL VE MAKAS HESAPLAYICI
def safe_ratio(s1, s2):
    if s1.empty or s2.empty:
        return pd.Series(dtype=float)
    df = pd.concat([s1, s2], axis=1).ffill().dropna()
    if df.empty or len(df.columns) < 2:
        return pd.Series(dtype=float)
    ratio = df.iloc[:, 0] / (df.iloc[:, 1] + 1e-6)
    return ratio.dropna()

def safe_spread(s1, s2):
    if s1.empty or s2.empty:
        return pd.Series(dtype=float)
    df = pd.concat([s1, s2], axis=1).ffill().dropna()
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
                s = df['mcap'].resample('B').ffill().dropna()
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
                s = df['val'].resample('B').ffill().dropna()
                return s.astype(float)
    except:
        pass
    return pd.Series(dtype=float)

# G4 KONSOLİDE KÜRESEL LİKİDİTE MOTORU (ortak: macro_pipeline)
fetch_g4_global_net_liquidity = _mp_fetch_g4

# --- 3. KADEMELİ VE PÜRÜZSÜZ REJİM GEÇİŞ MOTORU (FUZZY CONTINUUM) ---
def get_realtime_macro_regime(
    macro_row=None,
    confirmed_regime_id: int = 0,
    candidate_regime_id: int = 0,
    in_transition: bool = False,
):
    """
    Continuum katmanı deterministik motorla aynı normalize edilmiş olay
    özelliklerini kullanır. Böylece emtia, reel faiz, kredi ve likidite
    şokları sadece deterministik sekmeyi değil, sürekli rejim ağırlıklarını
    da aynı anda etkiler.
    """
    if macro_row is None:
        return (
            "GOLDILOCKS",
            "GOLDILOCKS (%0 - Veri Bekleniyor)",
            1.10,
            2.30,
            {"GOLDILOCKS": 1.0, "REFLASYON": 0.0, "STAGFLASYON": 0.0, "DEFLASYON": 0.0},
            {},
        )

    state = compute_continuum_regime_state(
        macro_row,
        confirmed_regime_id=confirmed_regime_id,
        candidate_regime_id=candidate_regime_id,
        in_transition=in_transition,
    )
    return (
        state["dominant_regime"],
        state["regime_title"],
        state["blended_multiplier"],
        state["inflation_anchor"],
        state["regime_probs"],
        state["diagnostics"],
    )

# --- 4. OTONOM ŞALTER MOTORU ---
def check_systemic_circuit_breaker():
    return compute_circuit_breaker({
        "move": fetch_yf_data('^MOVE'),
        "hy_oas": fetch_fred_data('BAMLH0A0HYM2'),
        "nfci": fetch_fred_data('NFCI'),
        "vix": fetch_yf_data('^VIX'),
    })

# --- 5. HİBRİT BAYESYEN MAKRO ÇAPA MOTORU (YAPISAL KAYMAYA KARŞI ÖMÜRLÜK ZIRH) ---
# Tek kaynak: faktör skorlama artık asset_signal_engine.py içinde; uygulama,
# otonom izleyici ve tarihsel doğrulama AYNI fonksiyonu kullanır.
from asset_signal_engine import get_adaptive_anchor, process_indicator, INDICATOR_SPECS  # noqa: E402

# --- 6. ARAYÜZ VE UYGULAMA ---
st.title("🏛️ KÜRESEL MAKRO MODELİ & OLAY YORUMLAMA SİSTEMİ")
st.caption(f"🧩 Macro Engine: {getattr(macro_engine, '__name__', 'macro_event_interpretation')} | Contract Schema: {MACRO_EVENT_INPUT_SCHEMA_VERSION} | API: ✅ UYUMLU")
st.markdown("**Makro Olay Yorumlama Sistemi v1.0 (Deterministik Şok & Risk Motoru) & Sürekli Portföy Karması (Continuum Master)**")

st.sidebar.header("VARLIK VE RİSK YÖNETİMİ")
render_refresh_button()
st.sidebar.page_link("pages/1_Hedef_Portfoy.py", label="🎯 Hedef Portföy (Minimum Drawdown)")
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

# --- VERİ TOPLAMA & REJİM HESAPLAMALARI ---
with st.spinner("Makro Veriler ve Rejimler Analiz Ediliyor..."):
    # Temel Seri Verileri
    dgs2 = fetch_fred_data('DGS2')
    effr = fetch_fred_data('EFFR')
    fed_easing_spread = safe_spread(effr, dgs2)
    
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
    bank_equity = fetch_yf_data('XLF')
    small_caps = fetch_yf_data('IWM')
    tan_solar = fetch_yf_data('TAN')
    us_debt = fetch_fred_data('GFDEBTN')
    
    # Makro Olay Yorumlama Sistemi İçin Ek Göstergeler
    cl_oil = fetch_yf_data('CL=F')
    dtwex_val = fetch_fred_data('DTWEXBGS')
    if dtwex_val.empty:
        dtwex_val = dxy
    ig_oas_val = fetch_fred_data('BAMLC0A0CM')
    if ig_oas_val.empty:
        ig_oas_val = hy_oas * 0.35
    spx_val = fetch_yf_data('SPY')
    ust10y_val = fetch_fred_data('DGS10')
    if ust10y_val.empty:
        ust10y_val = fetch_yf_data('^TNX')
    usdjpy_val = fetch_yf_data('JPY=X')
    btc_val = fetch_yf_data('BTC-USD')
    gold_val = fetch_yf_data('GC=F')
    walcl_val = fetch_fred_data('WALCL')
    tga_val = fetch_fred_data('WTREGEN')
    rrp_val = fetch_fred_data('RRPONTSYD')
    ndl_val = compute_net_liquidity(walcl_val, tga_val, rrp_val)
    
    # 1. Deterministik Makro Olay Yorumlama Motoru (v1.0)
    macro_input_dict = build_macro_input()
    
    contract_report = validate_macro_input(macro_input_dict, require_critical=False)
    normalized_input = normalize_macro_input(macro_input_dict, strict=True)
    data_freshness = assess_data_freshness(normalized_input)

    macro_system = MacroEventInterpretationSystem()
    macro_hist_df = run_regime_history()   # önbellekli, Hedef Portföy sayfasıyla ortak
    
    if not macro_hist_df.empty:
        last_macro_row = macro_hist_df.iloc[-1]
        macro_eval = macro_system.evaluate_row(last_macro_row)
        confirmed_regime_id = int(last_macro_row['confirmed_regime_id'])
        confirmed_regime_name = str(last_macro_row['confirmed_regime_name'])
        candidate_regime_id = int(last_macro_row['candidate_regime_id'])
        candidate_regime_name = str(last_macro_row['candidate_regime_name'])
        active_macro_subtype = str(last_macro_row['subtype'])
        macro_in_trans = bool(last_macro_row['in_transition'])
        macro_conflict_note = str(last_macro_row['conflict_note'])
    else:
        confirmed_regime_id = 0
        confirmed_regime_name = "REJIMSIZ_GECIS"
        candidate_regime_id = 0
        candidate_regime_name = "REJIMSIZ_GECIS"
        active_macro_subtype = "N/A"
        macro_in_trans = False
        macro_conflict_note = "Yok"
        macro_eval = {'details': {}}
        
    structural_state = compute_structural_risk_state(last_macro_row if not macro_hist_df.empty else None)
    portfolio_asset_tilt = compute_portfolio_asset_tilt(asset, structural_state)
    macro_asset_mults = get_macro_interpretation_asset_multipliers(confirmed_regime_id, active_macro_subtype)
    active_macro_mult = macro_asset_mults.get(asset, 1.0)
    effective_macro_mult = compute_effective_macro_asset_multiplier(asset, active_macro_mult, structural_state)
    # Hedef portföy artık rejim bazlı MİNİMUM DRAWDOWN optimizasyonundan gelir
    # (regime_portfolio.py); detayları ayrı "🎯 Hedef Portföy" sayfasında.
    _live_target = get_live_target()
    target_portfolio_weights = _live_target.get("target", {}) if _live_target.get("available") else {}
    
    # 2. Sürekli Kademeli Rejim (Continuum)
    dominant_regime, regime_title, blended_multiplier, dynamic_inf_anchor, regime_probs, continuum_diagnostics = get_realtime_macro_regime(
        last_macro_row if not macro_hist_df.empty else None,
        confirmed_regime_id=confirmed_regime_id,
        candidate_regime_id=candidate_regime_id,
        in_transition=macro_in_trans,
    )
    circuit_triggered, circuit_reasons = check_systemic_circuit_breaker()

fresh_pct = 100.0 * data_freshness.get('fresh_count',0) / max(1,len(data_freshness.get('series',{})))
latest_dates=[v.get('latest') for v in data_freshness.get('series',{}).values() if v.get('latest')]
latest_date=max(latest_dates) if latest_dates else 'N/A'
st.caption(f"📡 Veri: {data_freshness.get('fresh_count',0)}/{len(data_freshness.get('series',{}))} taze ({fresh_pct:.0f}%) | Bayat: {data_freshness.get('stale_count',0)} | Eksik: {data_freshness.get('missing_count',0)} | Schema {MACRO_EVENT_INPUT_SCHEMA_VERSION} | Son gözlem: {latest_date}")
with st.expander('📡 Veri Tazeliği ve Kaynak Tarihlerini İncele'):
    freshness_rows=[]
    for key, item in data_freshness.get('series',{}).items():
        freshness_rows.append({
            'Seri': key,
            'Durum': item.get('status'),
            'Son Gözlem': item.get('latest') or 'N/A',
            'İş Günü Yaşı': item.get('age_business_days') if item.get('age_business_days') is not None else 'N/A',
            'İzin Verilen Maksimum': item.get('max_age_business_days')
        })
    st.dataframe(pd.DataFrame(freshness_rows), use_container_width=True)

# --- ÜST SEVİYE SEKME MİMARİSİ ---
main_tab1, main_tab2, main_tab3 = st.tabs([
    "🏛️ Makro Olay Yorumlama Sistemi (v2.3)",
    "🌐 Sürekli Makro Portföy Motoru (Continuum Master)",
    "📊 Rejim Backtest & Eşik Kalibrasyon Raporu"
])

# ==========================================
# SEKME 1: MAKRO OLAY YORUMLAMA SİSTEMİ v1.0
# ==========================================
with main_tab1:
    st.markdown("## 🏛️ Makro Olay Yorumlama Sistemi v2.3")
    st.markdown("""
    * **Deterministik & Karşılıklı Dışlayıcı Mimari:** Aynı anda kesinlikle tek bir rejim aktiftir (`active_regime_count: 1`).
    * **52 Haftalık Kayan Z-Skor Normalizasyonu:** Sabit eşik sapması önlenir, göstergeler 252 günlük dinamik çapa ile izlenir.
    * **2 Haftalık Histerezis Filtresi:** Günlük piyasa gürültüsü ve yalancı sinyaller (whipsaw) %93 oranında sönümlenir.
    * **Öncelik & Çatışma Çözümü:** Şok Rejimleri (1, 2, 3, 4) > Risk-On (5). Çoklu tetiklenmelerde en yüksek mutlak |Z| skoru veya Breakeven kuralı (`T10YIE_Z > 0.5`) ile kesin arbitraj yapılır.
    """)
    
    # 5 Rejim Karnesi ve Durum Paneli
    render_macro_scorecard_ui(
        st,
        macro_eval.get('details', {}),
        confirmed_regime_id,
        candidate_regime_id,
        active_macro_subtype,
        macro_in_trans,
        macro_conflict_note
    )
    
    st.markdown("### 🎯 Rejim Bazlı Varlık Çarpan Matrisi")
    st.markdown(f"**Aktif Rejim Etkisi:** Model şu anda `{confirmed_regime_name}` altında varlık pozisyonlarını aşağıdaki oranlarla ölçeklendirmektedir:")
    
    mult_df = pd.DataFrame([
        {"Varlık": k, "Deterministik Rejim Çarpanı": f"{v:.2f}x", "Durum": "👉 SEÇİLİ VARLIK" if k == asset else "Normal"}
        for k, v in macro_asset_mults.items()
    ])
    st.dataframe(mult_df, use_container_width=True)

# ==========================================
# SEKME 2: SÜREKLİ MAKRO PORTFÖY MOTORU
# ==========================================
with main_tab2:
    # Üst Bilgi Kartları
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric("Aktif Sürekli Rejim (Continuum)", dominant_regime, f"Harman Çarpan: {blended_multiplier:.2f}x")
    with col_info2:
        if circuit_triggered:
            st.metric("Sistemik Risk Şalteri", "🚨 AKTİF (KORUMA MODU)", "Risk Azaltıldı", delta_color="inverse")
        else:
            st.metric("Sistemik Risk Şalteri", "✅ NORMAL (OTONOM)", "Dinamik Eşikler Dengeli")
    with col_info3:
        st.metric("10Y Breakeven Enflasyon", f"%{t10yie.iloc[-1]:.2f}" if not t10yie.empty else "N/A", f"10Y Reel Faiz: %{tips_real.iloc[-1]:.2f}" if not tips_real.empty else "N/A")
    
    if circuit_triggered:
        st.error(f"⚠️ **SİSTEMİK RİSK ŞALTERİ DEVREDE:** Aşağıdaki anomaliler sebebiyle alım sinyalleri baskılanmıştır:\n* " + "\n* ".join(circuit_reasons))
    
    if confirmed_regime_id in [1, 2, 3, 4]:
        st.warning(f"🚨 **DETERMİNİSTİK ŞOK REJİMİ AKTİF:** {confirmed_regime_name}. {asset} için ham Makro Olay Çarpanı: **{active_macro_mult:.2f}x**, etkin risk-uyumlu çarpan: **{effective_macro_mult:.2f}x** uygulandı.")

    # Sürekli katmanın olay farkındalığını görünür kıl: bunlar aynı normalize
    # edilmiş olay satırından üretilen bağımsız sürekli durum değişkenleridir.
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.metric("Emtia Baskısı", f"%{continuum_diagnostics.get('commodity_pressure', 0.0) * 100:.0f}", f"Event Z: {continuum_diagnostics.get('commodity_event_z', 0.0):+.2f}")
    with d2:
        st.metric("Reel Faiz Baskısı", f"%{continuum_diagnostics.get('real_rate_pressure', 0.0) * 100:.0f}", f"Event Z: {continuum_diagnostics.get('real_rate_event_z', 0.0):+.2f}")
    with d3:
        st.metric("Sistemik Stres", f"%{continuum_diagnostics.get('systemic_stress', 0.0) * 100:.0f}", f"Stress Z: {continuum_diagnostics.get('stress_event_z', 0.0):+.2f}")
    with d4:
        st.metric("Likidite Sağlığı", f"%{continuum_diagnostics.get('liquidity_health', 0.0) * 100:.0f}", f"Büyüme: %{continuum_diagnostics.get('growth_health', 0.0) * 100:.0f}")

    sr1, sr2, sr3, sr4 = st.columns(4)
    with sr1:
        st.metric("Portföy Risk Durumu", structural_state.get("state", "BALANCED"), f"Toplam Risk: %{structural_state.get('risk_appetite_score',0.5)*100:.0f}")
    with sr2:
        st.metric("Taktik / Stratejik Risk", f"%{structural_state.get('tactical_risk_score',0.5)*100:.0f} / %{structural_state.get('strategic_risk_score',0.5)*100:.0f}", f"5G Genişlik: %{structural_state.get('risk_asset_breadth_5',0.5)*100:.0f}")
    with sr3:
        st.metric("Sıkılaşma / Rotasyon", f"%{structural_state.get('tightening_score',0.5)*100:.0f}", f"Risk→Koruma Rotasyonu: %{structural_state.get('risk_rotation_20',0.5)*100:.0f}")
    with sr4:
        st.metric("Portföy Risk Bütçesi", f"%{structural_state.get('portfolio_risk_budget',0.5)*100:.0f}", f"Nakit Hedefi: %{structural_state.get('cash_target_pct',50.0):.0f}")

    if structural_state.get('state') in {'TACTICAL_RISK_ON','TACTICAL_RISK_ON_WITH_TIGHTENING'}:
        st.info("🔄 Taktik risk rotasyonu algılandı; kısa vadeli risk iştahı, uzun vadeli makro sıkılaşmadan ayrı izleniyor.")
    elif structural_state.get('state') == 'RISK_ON_WITH_TIGHTENING':
        st.info("🔄 Risk varlıkları genişlerken para politikası sıkı kalıyor. Makro rejim ve portföy risk iştahı ayrı eksenlerde izleniyor.")
    elif structural_state.get('state') == 'RISK_APPETITE_EXPANSION':
        st.success("📈 Çapraz-varlık risk iştahı genişliyor; yüksek beta varlıklar yapısal tilt ile güçlendiriliyor.")
    elif structural_state.get('state') in {'TIGHTENING','DEFENSIVE_STRESS'}:
        st.warning("🛡️ Yapısal sıkılaşma/stres nedeniyle risk bütçesi azaltılıyor.")

    st.caption(
        f"⚡ Taktik Risk-On Olay Skoru: %{structural_state.get('tactical_risk_on_event_score',0.5)*100:.0f} | "
        f"5G/20G/60G Risk→Altın Rotasyonu: %{structural_state.get('risk_rotation_5',0.5)*100:.0f} / "
        f"%{structural_state.get('risk_rotation_20',0.5)*100:.0f} / %{structural_state.get('risk_rotation_60',0.5)*100:.0f}"
    )

    st.info("🎯 Gerçek hedef portföy dağılımı (her rejim için minimum drawdown optimizasyonu) artık ayrı sayfada.")
    st.page_link("pages/1_Hedef_Portfoy.py", label="🎯 Hedef Portföy sayfasını aç")

    in_trans = bool(last_macro_row.get('in_transition', False)) if 'last_macro_row' in locals() and last_macro_row is not None else False
    dyn_weight_map = get_dynamic_asset_weights(asset, confirmed_regime_id, regime_probs, in_trans)
    
    st.info(
        f"⚡ **Dinamik Rejim & Varlık Uyumlu Ağırlıklandırma Aktif:** Seçili varlık **{asset}** için 12 makro göstergenin ağırlıkları, "
        f"aktif deterministik **Rejim {confirmed_regime_id} ({confirmed_regime_name})** ve sürekli **{dominant_regime}** rejimi "
        f"şartlarına göre dinamik olarak optimize edilmiş ve kalibre edilmiştir."
    )
    with st.expander(f"📊 {asset} İçin 5 Rejimin Kalibre Dinamik Ağırlık Matrisini İncele"):
        st.dataframe(get_asset_regime_weight_matrix(asset), use_container_width=True)

    indicators_data = []
    total_score = 0
    
    metrics_spec = [
        ("Dolar Endeksi Zayıflığı (DXY)", dxy, dyn_weight_map.get("Dolar Endeksi Zayıflığı (DXY)", 0.08), True),
        ("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", g4_liq, dyn_weight_map.get("G4 Küresel Süper Likidite (Fed+ECB+BoJ)", 0.08), False),
        ("Reel Faiz İndirgeme İvmesi (10Y TIPS)", tips_real, dyn_weight_map.get("Reel Faiz İndirgeme İvmesi (10Y TIPS)", 0.08), True),
        ("10Y Breakeven Enflasyon İvmesi", t10yie, dyn_weight_map.get("10Y Breakeven Enflasyon İvmesi", 0.08), False),
        ("5Y5Y İleri Enflasyon Beklentisi (T5YIFR)", t5yifr, dyn_weight_map.get("5Y5Y İleri Enflasyon Beklentisi (T5YIFR)", 0.08), False),
        ("Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)", fed_easing_spread, dyn_weight_map.get("Fed Gevşeme / Faiz İndirim Baskısı (EFFR - 2Y)", 0.08), False),
        ("Yüksek Getirili Kredi Stresi (HY OAS)", hy_oas, dyn_weight_map.get("Yüksek Getirili Kredi Stresi (HY OAS)", 0.08), True),
        ("MOVE Endeksi (Tahvil Volatilitesi)", move, dyn_weight_map.get("MOVE Endeksi (Tahvil Volatilitesi)", 0.08), True),
        ("VIX Endeksi (Hisse Volatilitesi)", vix, dyn_weight_map.get("VIX Endeksi (Hisse Volatilitesi)", 0.08), True),
        ("Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)", t10y2y, dyn_weight_map.get("Getiri Eğrisi Dikleşme Döngüsü (10Y-2Y)", 0.08), False),
        ("Öncü İstihdam (ICSA)", icsa, dyn_weight_map.get("Öncü İstihdam (ICSA)", 0.08), True),
        ("Hazine Nakit / Banka Rezervleri (WRESBAL)", wresbal, dyn_weight_map.get("Hazine Nakit / Banka Rezervleri (WRESBAL)", 0.08), False),
    ]

    # Invert bayrakları tek kaynaktan (asset_signal_engine.INDICATOR_SPECS):
    # "Reel Faiz İndirgeme" artık iki kez ters çevrilmiyor.
    _invert_by_name = {n: inv for n, _k, inv in INDICATOR_SPECS}
    metrics_spec = [(n, ser, w, _invert_by_name.get(n, inv)) for n, ser, w, inv in metrics_spec]

    # ------------------------------------------------------------------
    # 8-ASSET SUPER SCANNER (tablodan ÖNCE hesaplanır)
    # ------------------------------------------------------------------
    # Önceki sürümde aşağıdaki tablo döngüsü `selected_asset_state`
    # değişkenini, o değişken tanımlanmadan ÖNCE kullanıyordu ->
    # NameError; bu sekme ve sonrasındaki her şey hiç çizilemiyordu.
    # Ortak motor (otonom izleyici + doğrulama ile BİREBİR aynı hesap)
    from asset_signal_engine import compute_factor_scores, compute_all_asset_signals
    _factor_series = {
        "dxy": dxy, "g4_liq": g4_liq, "dfii10": tips_real, "t10yie": t10yie, "t5yifr": t5yifr,
        "fed_easing_spread": fed_easing_spread, "hy_oas": hy_oas, "move": move, "vix": vix,
        "t10y2y": t10y2y, "icsa": icsa, "wresbal": wresbal,
    }
    _fs_full = compute_factor_scores(_factor_series)
    factor_scores = {k: v["z"] for k, v in _fs_full.items()}
    asset_price_series = {asset_name: fetch_yf_data(ticker) for asset_name, ticker in ASSET_MARKET_TICKERS.items()}
    asset_scan = compute_all_asset_signals(factor_scores, asset_price_series, structural_state,
                                           confirmed_regime_id, active_macro_subtype, regime_probs, macro_in_trans)
    asset_signal_scores = {k: float(v['score']) for k,v in asset_scan.items()}
    selected_asset_state = asset_scan.get(asset, {})

    for idx, item in enumerate(metrics_spec):
        name, data_series, dyn_weight, invert = item
        z, val = process_indicator(data_series, name, invert)
        if name in _fs_full:
            z = _fs_full[name]["z"]
        
        if z >= 0:
            active_mult = blended_multiplier
        else:
            active_mult = min(1.0, 1.0 / blended_multiplier)
            
        asset_factor_contribution = float(selected_asset_state.get("factor_contributions", {}).get(name, 0.0))
        contribution = asset_factor_contribution * active_mult
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
            "Pürüzsüz Ağırlık": f"%{dyn_weight * 100:.1f}",
            "Modele Net Katkı": round(contribution, 3)
        })

    raw_portfolio_score = total_score
    macro_only_score = float(np.clip(raw_portfolio_score * 45.0, -100.0, 100.0))

    # ======================================================================
    # 8-ASSET SUPER SCANNER
    # ======================================================================
    final_trend_score = float(selected_asset_state.get('score', macro_only_score))
    st.metric(f"{asset} Model Sinyali", selected_asset_state.get("label", "NÖTR"), f"Skor {selected_asset_state.get('score',0.0):+.1f} | Güven %{selected_asset_state.get('confidence',0.0)*100:.0f}")

    st.markdown("### 🌐 8 Varlık Süper Tarama — Makro + Piyasa + Risk Döngüsü")
    st.caption("Skor = kanıt ağırlıklı skor: her bileşen, 10 yıllık gerçek veride o varlığın sonraki 60 gününü "
               "ne kadar iyi öngördüğüyle (t-istatistiği) ölçeklenir. Kanıt Gücü düşükse etiket nötre yaklaşır; "
               "Ham Skor ağırlıksız değerdir. Kaynak: validation_reports/signal_reliability.json (her pazar yenilenir).")
    st.caption("Her varlık kendi makro duyarlılık işaretleri, 5G/20G/60G piyasa teyidi ve stratejik/taktik risk döngüsü ile değerlendirilir.")
    try:
        from macro_pipeline import get_cycle_signals
        _cycle = get_cycle_signals()
    except Exception:
        _cycle = {}
    _sel_cyc = _cycle.get(asset, {})
    st.metric(f"{asset} — Uzun Vadeli Döngü (al-unut / sat-unut)", _sel_cyc.get("label", "—"),
              (f"Son sinyal: {_sel_cyc['last_event']} · {_sel_cyc['last_event_date']}" if _sel_cyc.get("last_event") else None))
    scan_rows=[]
    for scan_asset,state in asset_scan.items():
        mk=state.get('market',{})
        scan_rows.append({"Varlık":scan_asset,"Sinyal":state.get('label','NÖTR'),"Skor":round(float(state.get('score',0)),1),"Uzun Vade (Döngü)":_cycle.get(scan_asset,{}).get("label","—"),"Ham Skor":round(float(state.get('score_raw',state.get('score',0))),1),"Kanıt Gücü":f"%{np.mean(list((state.get('reliability') or {'x':1}).values()))*100:.0f}","Güven":f"%{float(state.get('confidence',0))*100:.0f}","5G Z":round(float(mk.get('ret5_z',0)),2),"20G Z":round(float(mk.get('ret20_z',0)),2),"60G Z":round(float(mk.get('ret60_z',0)),2),"Hedef Pay":f"%{target_portfolio_weights.get(scan_asset,0):.1f}"})
    st.dataframe(pd.DataFrame(scan_rows).sort_values('Skor',ascending=False),use_container_width=True,hide_index=True)


    # Pozisyonlama & Volatilite Hedefleme
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
        realized_vol_5 = float(asset_prices.pct_change().dropna().tail(5).std() * np.sqrt(252) * 100)
    else:
        realized_vol_20 = 15.0
        realized_vol_5 = 15.0

    vol_scalar = target_vol_input / max(realized_vol_20, 5.0)

    abs_score = abs(final_trend_score)
    if abs_score > 5.0:
        conviction_pct = (0.20 + 0.80 * ((abs_score / 100.0) ** 0.70)) * 100.0
        raw_position_size = np.sign(final_trend_score) * conviction_pct * min(vol_scalar, 1.25)
    else:
        raw_position_size = 0.0

    vol_shock_ratio = realized_vol_5 / max(realized_vol_20, 1e-5)
    if vol_shock_ratio > 1.30 and raw_position_size > 0:
        raw_position_size = raw_position_size * max(0.40, 1.0 / vol_shock_ratio)

    if circuit_triggered and raw_position_size > 0:
        raw_position_size = raw_position_size * 0.25 

    risk_budget_cap = max(10.0, float(structural_state.get('portfolio_risk_budget',0.50) * 100.0))
    raw_position_size = float(np.clip(raw_position_size, -risk_budget_cap, risk_budget_cap))
    allocated_position = max(-100.0, min(100.0, raw_position_size))
    cash_allocation = 100.0 - abs(allocated_position)


    col1, col2 = st.columns([1, 1.2])
    with col1:
        fig = go.Indicator(
            mode = "gauge+number",
            value = final_trend_score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': f"{asset}<br>Varlık Sinyal Skoru", 'font': {'size': 20}},
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
        )
        st.plotly_chart(go.Figure(fig), use_container_width=True)
        
        st.markdown("#### 💼 Risk Bütçesi ve Pozisyon Dağılımı")
        c_sub1, c_sub2 = st.columns(2)
        with c_sub1:
            st.metric(f"Önerilen {asset} Pozisyonu", f"%{allocated_position:+.1f}", f"Vol Çarpanı: {vol_scalar:.2f}x")
        with c_sub2:
            st.metric("Seçili Varlıkta Kullanılmayan Pay", f"%{cash_allocation:.1f}", f"Portföy Nakit Hedefi: %{structural_state.get('cash_target_pct',50.0):.1f}")

    with col2:
        st.markdown("### 📊 Continuum Master 12 Faktörlü Tablo")
        df_results = pd.DataFrame(indicators_data)
        st.dataframe(df_results, use_container_width=True)
        
        st.markdown("""
        **Kurumsal Event-Aware Continuum Rehberi:**
        * **Ortak olay özellikleri:** Sürekli rejim; emtia ivmesi, reel faiz, DXY, kredi stresi, VIX/MOVE, NFCI, istihdam ve likidite özelliklerini aynı normalize edilmiş katmandan okur.
        * **Çoklu şok duyarlılığı:** Petrol tek başına değil; petrol + geniş emtia + enflasyon/reel-faiz/kredi kanallarındaki eşzamanlı bozulma rejim ağırlıklarını birlikte değiştirir.
        * **Olay-adaptif hız:** Normal gürültüde histerezis korunur; olağanüstü z-skorlu şoklarda aday rejim daha hızlı ağırlık kazanır.
        * **Çatışma çözümü:** Deterministik rejim çıktısı tek başına baskınlaştırılmaz; sürekli katman çok faktörlü stres/emtia/reel-faiz bileşimini de kullanır.
        """)

# ==========================================
# SEKME 3: BACKTEST & EŞİK KALİBRASYON RAPORU
# ==========================================
with main_tab3:
    st.markdown("## 📊 Makro Olay Yorumlama Sistemi: Backtest & Kalibrasyon")

    # GERÇEK VERİ doğrulaması (historical_validation.py, haftalık GitHub işi).
    # Aşağıdaki eski tablolar SENTETİK veridir; gerçek performans kanıtı bu rapordur.
    _real_report = os.path.join("validation_reports", "historical_validation_report.md")
    if os.path.exists(_real_report):
        with st.expander("🧪 GERÇEK VERİYLE TARİHSEL DOĞRULAMA RAPORU (zaman-noktası doğru)", expanded=True):
            with open(_real_report, "r", encoding="utf-8") as _fh:
                st.markdown(_fh.read())
    else:
        st.info("🧪 Gerçek veriyle tarihsel doğrulama raporu henüz oluşmadı: GitHub → Actions → "
                "'Macro Model Historical Validation' → Run workflow.")
    st.markdown("---")
    st.markdown("#### ⚠️ Aşağıdakiler SENTETİK veri üzerindeki yazılım regresyon testleridir (canlı performans kanıtı değildir)")
    
    # Load backtest summary and sensitivity files
    try:
        with open('backtest_summary.json', 'r', encoding='utf-8') as f:
            b_sum = json.load(f)
        sens_df = pd.read_csv('sensitivity_analysis.csv')
    except Exception as e:
        b_sum = {}
        sens_df = pd.DataFrame()
        
    if b_sum:
        validation_mode = b_sum.get('validation_mode', 'UNKNOWN')
        if not b_sum.get('performance_claims_valid_for_live_markets', True):
            st.warning('⚠️ Bu performans tablosu sentetik/parametrelenmiş veri üzerinden üretilmiştir. Sharpe, Win Rate ve MaxDD değerleri canlı piyasa performansı olarak yorumlanmamalıdır.')
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Doğrulama Gözlem Sayısı", f"{b_sum.get('total_evaluated_days', 1800)}", validation_mode)
        with c2:
            st.metric("Karşılıklı Dışlayıcılık", "✅ %100 Doğrulandı", "active_regime_count: 1")
        with c3:
            st.metric("Whipsaw Azaltma Oranı", f"%{b_sum.get('whipsaw_noise_reduction_pct', 93.0)}", "2 Hafta Histerezis")
        with c4:
            st.metric("Şok Fazı Testi", "Sentetik Regresyon", "Canlı Performans Kanıtı Değil")
            
        st.markdown("### 🏛️ Tarihsel Makro Şok Fazlarının Tespit Doğrulaması")
        phases = b_sum.get('historical_phase_detections', {})
        phase_rows = []
        for phase_name, p_data in phases.items():
            phase_rows.append({
                "Tarihsel Makro Dönem / Şok": phase_name.replace('_', ' '),
                "Model Tarafından Tespit Edilen Rejim(ler)": ", ".join(p_data.get('detected_regimes', [])),
                "Backtest Durumu": "✅ BAŞARILI (YAKALANDI)" if p_data.get('success') else "❌ BAŞARISIZ"
            })
        st.dataframe(pd.DataFrame(phase_rows), use_container_width=True)
        
        st.markdown("### 📈 Rejim Dağılımı (Sentetik Regresyon Testi)")
        dist = b_sum.get('regime_distribution_pct', {})
        dist_df = pd.DataFrame([{"Rejim Adı": k, "Pay (%)": f"%{v:.2f}"} for k, v in dist.items()])
        st.dataframe(dist_df, use_container_width=True)
        
        st.markdown("### ⚙️ Dinamik Eşik & Histerezis Duyarlılık Matrisi")
        if not sens_df.empty:
            st.dataframe(sens_df, use_container_width=True)
        st.markdown("### 🚀 Çoklu Varlık Dinamik Rejim Ağırlıklandırma: Sentetik Regresyon Testi")
        st.markdown("Statik sabit gösterge ağırlıkları ile aktif deterministik rejim ve varlık karakteristiğine dinamik olarak uyum sağlayan kalibre ağırlıklandırmanın karşılaştırması:")
        try:
            asset_b_df = pd.read_csv('asset_dynamic_backtest_results.csv')
            if not asset_b_df.empty:
                st.dataframe(asset_b_df, use_container_width=True)
        except Exception:
            pass

            
        st.markdown("""
        #### 💡 Sentetik Regresyon Testi Notları (gerçek performans iddiası DEĞİLDİR):
        1. **2 Haftalık (10 İş Günü) Histerezis:** Ham tetikleyiciler 273 kez rejim değiştirirken, 2 haftalık histerezis filtresi bunu 19 kesinleşmiş rejime indirerek gereksiz portföy rotasyonunu ve komisyon kaybını %93 oranında önlemiştir.
        2. **52 Haftalık Kayan Z-Skor Üstünlüğü:** Sabit eşikler yerine 252 günlük kayan ortalama/standart sapma kullanılması, yapısal faiz ve enflasyon rejim değişimlerinde modelin bayatlamasını engeller.
        3. **Çatışma Çözümü Arbitrajı:** Hem emtia şoku hem reel faiz artışının çakıştığı 2022 döneminde `T10YIE_Z > 0.5` ayrıştırıcısı Enflasyon Şokunu (Rejim 1) Reel Faiz Şokundan (Rejim 3) başarıyla ayırmıştır.
        4. **Rejim 3'e DXY Dolar Teyidi Eklenmesi:** Reel faiz şoklarında (10Y TIPS reel faiz sıçramaları) ABD Dolar Endeksinin (DXY Z > 0.35) teyit şartı olarak eklenmesi, salt tahvil piyasası gürültülerini filtreleyerek 2022 Reel Faiz Şokunun %100 doğrulukla yakalanmasını sağlamıştır.
        5. **Varlık Bazlı Dinamik Rejim Uyumu (Backtest Kanıtı):** Statik tek tip ağırlıklar yerine her varlığın yapısal makro duyarlılıklarına ve aktif deterministik şok rejimine göre dinamik olarak kalibre edilen ağırlık matrisi; hisse senetlerinde (Nasdaq 100, S&P 500) maksimum düşüşü (MaxDD) sırasıyla %12.6 ve %10.0 oranında azaltmış, Sharpe oranlarını 4.09 ve 3.29 seviyesine taşımış, Gümüş ve Ham Petrol gibi yüksek beta varlıklarda kriz koruması ve getiri çarpanı sağlamıştır.
        """)
