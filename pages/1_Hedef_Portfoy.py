"""🎯 Hedef Portföy — rejim bazlı minimum drawdown portföyleri (ayrı sayfa)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Hedef Portföy (Min Drawdown)", layout="wide")

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


from macro_pipeline import (  # noqa: E402
    fetch_asset_prices, get_live_target, render_refresh_button, run_regime_history,
)
from macro_event_interpretation import REGIME_NAMES  # noqa: E402
from regime_portfolio import CASH_KEY  # noqa: E402

st.sidebar.header("🎯 HEDEF PORTFÖY")
render_refresh_button()

st.title("🎯 Hedef Portföy — Rejime Uyumlu, Düşüş Kontrollü")
st.caption(
    "Öncelik minimum düşüş: 9 kurumsal strateji (risk paritesi / trend / uzun vadeli döngü × "
    "%10 vol hedefi / rejime göre vol hedefi / düşüş freni) gerçek 10+ yıllık veride ÖRNEKLEM DIŞI yarışır; "
    "maksimum düşüşü %12 içinde kalanlar arasından en yüksek getirili olan canlı hedef olur. "
    "Kaldıraç ve açığa satış yok; yatırılmayan kısım nakit."
)

with st.spinner("Rejim, döngü sinyalleri ve hedef portföy hesaplanıyor..."):
    live = get_live_target()

if not live.get("available"):
    st.error("Veri alınamadı; lütfen 'Canlı Verileri Yenile' ile tekrar deneyin.")
    st.stop()

ports = live["portfolios"]
assets = ports.get("assets", [])
structural = live["structural"]
conf, cand, tr = live["confirmed"], live["candidate"], live["in_transition"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Onaylı Rejim", f"{conf}: {REGIME_NAMES.get(conf, '')}")
c2.metric("Aday Rejim", f"{cand}: {REGIME_NAMES.get(cand, '')}", "⏳ geçişte (60/40 harman)" if tr and cand != conf else "🔒 sabit")
c3.metric("Yatırılan (vol hedefli)", f"%{100 - live['target'].get(CASH_KEY, 0):.0f}", structural.get("state", ""))
c4.metric("Nakit", f"%{live['target'].get(CASH_KEY, 0):.0f}", f"veri: {live['as_of']}")

from regime_portfolio import STRATEGY_LABELS  # noqa: E402
from macro_pipeline import get_cycle_signals  # noqa: E402

st.markdown("## 🔄 Uzun Vadeli Döngü Sinyalleri (dipten al-unut / tepeden sat-unut)")
st.caption("Her varlık kendi 2-3 yıllık değer ortalamasına göre ne kadar ucuz/pahalı? Dip/tepe bantları varlığın kendi "
           "geçmişinden otomatik uyarlanır; dönüş teyidi ve parametreler her pazar örneklem dışı yarışla yeniden seçilir. "
           "Tahvil (TLT) bu motorun dışında: faiz modeli + trend kuralı geçerli.")
try:
    _cyc = get_cycle_signals()
    _crow = []
    for a, c in _cyc.items():
        if not c.get("applicable", True):
            _crow.append({"Varlık": a, "Uzun vadeli sinyal": c["label"], "Değer z": "—", "Bant konumu": "—",
                          "Son sinyal": "—"})
            continue
        bp = c.get("band_position")
        _crow.append({
            "Varlık": a, "Uzun vadeli sinyal": c.get("label", "—"),
            "Değer z": f"{c['value_z']:+.2f}" if c.get("value_z") is not None else "—",
            "Bant konumu": "—" if bp is None or not np.isfinite(bp) else f"%{bp * 100:.0f} (0=dip, 100=tepe)",
            "Son sinyal": f"{c['last_event']} · {c['last_event_date']}" if c.get("last_event") else "henüz yok",
        })
    st.dataframe(pd.DataFrame(_crow), use_container_width=True, hide_index=True)
except Exception as _exc:
    st.caption(f"Döngü sinyalleri hesaplanamadı: {_exc}")

st.markdown("## 🏆 Strateji Seçimi (örneklem dışı yarış)")
_scores = (live.get("strategy_scores") or {}).get("strategies", {})
st.success(f"Canlı strateji: **{STRATEGY_LABELS.get(live['strategy'], live['strategy'])}**"
           + ("" if _scores else " — (henüz doğrulama sonucu yok; varsayılan. GitHub → Actions → "
              "'Macro Model Historical Validation' çalıştırılınca en iyi strateji otomatik seçilir.)"))
_rows = []
for k, lbl in STRATEGY_LABELS.items():
    sc = _scores.get(k, {})
    _rows.append({"Strateji": ("🏆 " if k == live["strategy"] else "") + lbl,
                  "Yıllık getiri": f"%{sc['cagr']*100:+.1f}" if sc else "—",
                  "Maks. düşüş": f"%{sc['max_dd']*100:.1f}" if sc else "—",
                  "Sharpe": f"{sc['sharpe']:.2f}" if sc and sc.get('sharpe') is not None else "—",
                  "Kazançlı ay": f"%{sc['win_month']*100:.0f}" if sc and sc.get('win_month') is not None else "—",
                  "Kazançlı yıl": f"%{sc['win_year']*100:.0f}" if sc and sc.get('win_year') is not None else "—",
                  "Calmar": f"{sc['calmar']:.2f}" if sc and sc.get('calmar') is not None else "—"})
st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
st.caption("Değerler örneklem dışıdır: her strateji geçmişte her hafta yalnızca o güne kadarki veriyle karar verdi. "
           "Öncelik: maks. düşüş ≤ %12 olanlar arasında en yüksek getiri. Kaldıraç yok; kalan nakit.")

with st.expander("Tüm stratejilerin güncel hedef ağırlıkları"):
    _all = live.get("all_targets", {})
    if _all:
        st.dataframe(pd.DataFrame({STRATEGY_LABELS.get(k, k): {a: round(v, 1) for a, v in w.items()} for k, w in _all.items()}),
                     use_container_width=True)

st.markdown("## 🧭 Aktif Hedef Portföy")
tgt = live["target"]
tdf = pd.DataFrame([{"Varlık": k, "Hedef Pay (%)": round(v, 2)} for k, v in tgt.items()])
col_a, col_b = st.columns([1, 1.3])
with col_a:
    st.dataframe(tdf, use_container_width=True, hide_index=True)
with col_b:
    fig = go.Figure(go.Bar(x=tdf["Hedef Pay (%)"], y=tdf["Varlık"], orientation="h",
                           text=[f"%{v:.1f}" for v in tdf["Hedef Pay (%)"]], textposition="auto"))
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="%")
    st.plotly_chart(fig, use_container_width=True)

st.markdown("## 📋 Referans: Her Rejim İçin Minimum Drawdown Portföyü (%100 riskli sepet, örneklem içi)")
rows = []
for rid in range(6):
    p = ports["portfolios"].get(rid)
    if not p:
        continue
    s, e = p.get("stats", {}), p.get("ew_stats", {})
    row = {"Rejim": f"{rid}: {REGIME_NAMES.get(rid, '')}", "Gün": s.get("days", 0),
           "Güven": f"%{p.get('trust', 0) * 100:.0f}"}
    for a in assets:
        row[a.split(" (")[0]] = f"%{p['weights'].get(a, 0) * 100:.0f}"
    if s.get("days"):
        row["Maks DD"] = f"%{s['max_drawdown'] * 100:.1f}"
        row["Eşit Ağ. Maks DD"] = f"%{e['max_drawdown'] * 100:.1f}"
        row["Yıllık Getiri"] = f"%{s['ann_return'] * 100:+.1f}"
        row["Eşit Ağ. Getiri"] = f"%{e['ann_return'] * 100:+.1f}"
    rows.append(row)
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
st.caption("Güven: rejimin geçmişteki gün sayısına göre (60+ gün = %100). Düşük güvenli rejimler tüm-dönem "
           "minimum drawdown portföyüne doğru çekilir. Aşağıdaki tablolar ÖRNEKLEM İÇİ sonuçtur; örneklem dışı "
           "(gerçekten önceden bilinerek) performans, haftalık tarihsel doğrulama raporundadır.")

st.markdown("## 📉 Aktif Rejimde Drawdown Karşılaştırması")
try:
    hist = run_regime_history()
    prices = pd.DataFrame(fetch_asset_prices()).sort_index().ffill()
    rets = prices.pct_change().dropna(how="all").fillna(0.0)
    regime = hist["confirmed_regime_id"].reindex(rets.index, method="ffill").shift(1).fillna(0).astype(int)
    sub = rets[regime == conf]
    if len(sub) > 5:
        w = np.array([ports["portfolios"][conf]["weights"].get(a, 0) for a in sub.columns])
        ew = np.full(len(sub.columns), 1 / len(sub.columns))
        fig2 = go.Figure()
        for name, vec in (("Min-DD rejim portföyü", w), ("Eşit ağırlık", ew)):
            cum = (1 + sub.to_numpy() @ vec).cumprod()
            dd = cum / np.maximum.accumulate(cum) - 1
            fig2.add_trace(go.Scatter(y=dd * 100, mode="lines", name=name))
        fig2.update_layout(height=320, yaxis_title="Drawdown %", xaxis_title=f"Rejim {conf} günleri (ardışık)",
                           margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Aktif rejim için yeterli tarihsel gün yok; tüm-dönem portföyü kullanılıyor.")
except Exception as exc:
    st.caption(f"Drawdown grafiği çizilemedi: {exc}")
