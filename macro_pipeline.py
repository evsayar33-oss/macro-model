"""
Macro Pipeline — shared, cached data + engine layer for every Streamlit page
=============================================================================
The main page (app.py) and the "🎯 Hedef Portföy" page both need the same
market data, the same regime history and the same regime portfolios. Keeping
them here (with st.cache_data) means:
  * both pages show identical numbers,
  * opening the second page does not re-download anything,
  * ONE "🔄 Canlı Verileri Yenile" button clears every cache and recomputes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Dict

import numpy as np
import pandas as pd
import requests
import streamlit as st

ASSET_TICKERS = {
    "Altın (XAU)": "GC=F", "Gümüş (XAG)": "SI=F", "Nasdaq 100 (NQ)": "QQQ",
    "S&P 500 (SPX)": "SPY", "Kripto (BTC)": "BTC-USD", "Ham Petrol (WTI)": "CL=F",
    "Bakır (HG)": "HG=F", "ABD Tahvili / Faiz (TLT)": "TLT",
}


# ----------------------------------------------------------------------
# Fetchers
# ----------------------------------------------------------------------
def _fred_client():
    try:
        key = st.secrets["FRED_API_KEY"]
    except Exception:
        return None
    try:
        from fredapi import Fred
        return Fred(api_key=key)
    except Exception:
        return None


def _fred_csv(series_id: str, start: datetime) -> pd.Series:
    """Key-free fallback (public fredgraph CSV endpoint)."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start:%Y-%m-%d}"
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    date_col = next((c for c in df.columns if c.lower() in {"date", "observation_date"}), df.columns[0])
    val_col = [c for c in df.columns if c != date_col][0]
    vals = pd.to_numeric(df[val_col].replace(".", np.nan), errors="coerce")
    return pd.Series(vals.values, index=pd.to_datetime(df[date_col], errors="coerce")).dropna()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_fred_data(series_id, days=2500):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    try:
        client = _fred_client()
        data = client.get_series(series_id, start_date, end_date) if client else _fred_csv(series_id, start_date)
        s = pd.Series(data)
        s.index = pd.to_datetime(s.index)
        s = s.resample('B').ffill().dropna()
        return s.astype(float)
    except Exception:
        try:
            s = _fred_csv(series_id, start_date)
            return s.resample('B').ffill().dropna().astype(float)
        except Exception:
            return pd.Series(dtype=float)


@st.cache_data(ttl=900, show_spinner=False)
def fetch_yf_data(ticker, days=2500):
    import yfinance as yf
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    try:
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if data.empty:
            data = yf.download(ticker, period="10y", progress=False)
        if data.empty:
            return pd.Series(dtype=float)
        s = data['Close'] if 'Close' in data.columns else data.iloc[:, 0]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        s = pd.Series(s.values.flatten(), index=pd.to_datetime(s.index))
        if s.index.tz is not None:
            s.index = s.index.tz_localize(None)
        s = s.resample('B').ffill().dropna()
        return s.astype(float)
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_g4_global_net_liquidity(days=2500):
    from asset_signal_engine import build_g4_net_liquidity
    return build_g4_net_liquidity(
        fetch_fred_data('WALCL', days), fetch_fred_data('WTREGEN', days), fetch_fred_data('RRPONTSYD', days),
        fetch_fred_data('ECBASSETSW', days), fetch_yf_data('EURUSD=X', days),
        fetch_fred_data('JPNASSETS', days), fetch_yf_data('JPY=X', days),
    )


# ----------------------------------------------------------------------
# Engine
# ----------------------------------------------------------------------
def build_macro_input() -> Dict[str, pd.Series]:
    from macro_event_interpretation import compute_net_liquidity
    dxy = fetch_yf_data('DX-Y.NYB')
    hy_oas = fetch_fred_data('BAMLH0A0HYM2')
    dtwex = fetch_fred_data('DTWEXBGS')
    if dtwex.empty:
        dtwex = dxy
    ig_oas = fetch_fred_data('BAMLC0A0CM')
    if ig_oas.empty:
        ig_oas = hy_oas * 0.35
    ust10y = fetch_fred_data('DGS10')
    if ust10y.empty:
        ust10y = fetch_yf_data('^TNX')
    return {
        'oil': fetch_yf_data('CL=F'), 'bdi': fetch_yf_data('BDRY'), 'hy_oas': hy_oas, 'ig_oas': ig_oas,
        'spx': fetch_yf_data('SPY'), 'ust10y': ust10y, 'ust2y': fetch_fred_data('DGS2'), 'dtwex': dtwex,
        'dxy': dxy, 'usdjpy': fetch_yf_data('JPY=X'), 'vix': fetch_yf_data('^VIX'), 'move': fetch_yf_data('^MOVE'),
        'btc': fetch_yf_data('BTC-USD'), 'dfii10': fetch_fred_data('DFII10'), 't10yie': fetch_fred_data('T10YIE'),
        'ndl': compute_net_liquidity(fetch_fred_data('WALCL'), fetch_fred_data('WTREGEN'), fetch_fred_data('RRPONTSYD')),
        'gold': fetch_yf_data('GC=F'), 'xag': fetch_yf_data('SI=F'), 'hg': fetch_yf_data('HG=F'),
        'dbb': fetch_yf_data('DBB'), 'nfci': fetch_fred_data('NFCI'), 'icsa': fetch_fred_data('ICSA'),
        'bank_equity': fetch_yf_data('XLF'), 'small_caps': fetch_yf_data('IWM'),
    }


@st.cache_data(ttl=900, show_spinner=False)
def run_regime_history() -> pd.DataFrame:
    from macro_event_interpretation import MacroEventInterpretationSystem
    return MacroEventInterpretationSystem().evaluate_history(build_macro_input())


def fetch_asset_prices() -> Dict[str, pd.Series]:
    return {a: fetch_yf_data(t) for a, t in ASSET_TICKERS.items()}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_regime_portfolios() -> Dict[str, Any]:
    from regime_portfolio import compute_regime_portfolios
    persisted = _monitor_state().get("regime_min_drawdown_portfolios") or {}
    if persisted:
        ports = {int(k): v for k, v in persisted.items()}
        first = next(iter(ports.values()))
        return {"assets": list(first.get("weights", {}).keys()), "portfolios": ports, "all": {}}
    hist = run_regime_history()
    if hist.empty:
        return {"assets": [], "portfolios": {}, "all": {}}
    return compute_regime_portfolios(hist['confirmed_regime_id'], fetch_asset_prices())


def _monitor_state() -> Dict[str, Any]:
    """Latest state persisted by the GitHub Actions monitor (runs every 2h
    with the same code). Heavy LP optimisations are taken from here so the
    Streamlit app does not burn CPU (Streamlit Cloud throttling)."""
    import json
    try:
        with open("backtest_summary.json", "r", encoding="utf-8") as fh:
            return (json.load(fh).get("autonomous_daily_monitor") or {}).get("current") or {}
    except Exception:
        return {}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_yf_long(ticker: str) -> pd.Series:
    """Long daily history (up to 20y) for the multi-year cycle engine."""
    import yfinance as yf
    try:
        d = yf.download(ticker, period="20y", interval="1d", progress=False, auto_adjust=False)
        if d is None or d.empty:
            return fetch_yf_data(ticker)
        s = d["Close"] if "Close" in d.columns else d.iloc[:, 0]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        s = pd.Series(s.values.flatten(), index=pd.to_datetime(s.index))
        if s.index.tz is not None:
            s.index = s.index.tz_localize(None)
        return s.resample("B").ffill().dropna().astype(float)
    except Exception:
        return fetch_yf_data(ticker)


def fetch_asset_prices_long() -> Dict[str, pd.Series]:
    return {a: fetch_yf_long(t) for a, t in ASSET_TICKERS.items()}


@st.cache_data(ttl=3600, show_spinner=False)
def get_cycle_signals() -> Dict[str, Dict[str, Any]]:
    """Long-horizon al-unut / sat-unut state per asset (cycle_engine.py)."""
    from cycle_engine import current_cycle_signal, load_cycle_params
    params = load_cycle_params()
    return {a: current_cycle_signal(a, s, params.get(a)) for a, s in fetch_asset_prices_long().items()}


@st.cache_data(ttl=3600, show_spinner=False)
def _live_strategy_target(strategy: str, confirmed: int, candidate: int, in_transition: bool) -> Dict[str, float]:
    from regime_portfolio import strategy_weights
    hist = run_regime_history()
    return strategy_weights(strategy, fetch_asset_prices_long(), hist['confirmed_regime_id'],
                            confirmed, candidate, in_transition)


def get_all_strategy_targets(confirmed: int, candidate: int, in_transition: bool) -> Dict[str, Dict[str, float]]:
    """The SELECTED strategy is computed live (≤1h cache). The others come from
    the GitHub Actions monitor's persisted state (no Streamlit CPU cost)."""
    from regime_portfolio import STRATEGY_LABELS, selected_strategy
    out: Dict[str, Dict[str, float]] = {}
    persisted = _monitor_state().get("all_strategy_targets") or {}
    for k, v in persisted.items():
        if k in STRATEGY_LABELS:
            out[k] = v
    chosen = selected_strategy()
    try:
        out[chosen] = _live_strategy_target(chosen, confirmed, candidate, in_transition)
    except Exception:
        pass
    return out


def get_live_target() -> Dict[str, Any]:
    """Active regime + every strategy's current weights; the live target is the
    strategy with the best OUT-OF-SAMPLE Calmar in the latest validation run."""
    from macro_event_interpretation import compute_structural_risk_state
    from regime_portfolio import load_strategy_scores, selected_strategy
    hist = run_regime_history()
    if hist.empty:
        return {"available": False}
    last = hist.iloc[-1]
    structural = compute_structural_risk_state(last)
    conf, cand, tr = int(last['confirmed_regime_id']), int(last['candidate_regime_id']), bool(last['in_transition'])
    all_targets = get_all_strategy_targets(conf, cand, tr)
    chosen = selected_strategy()
    if chosen not in all_targets and all_targets:
        chosen = next(iter(all_targets))
    return {
        "available": True, "confirmed": conf, "candidate": cand, "in_transition": tr,
        "structural": structural, "portfolios": get_regime_portfolios(),
        "strategy": chosen, "all_targets": all_targets, "strategy_scores": load_strategy_scores(),
        "target": all_targets.get(chosen, {}), "as_of": str(hist.index[-1].date()),
    }


# ----------------------------------------------------------------------
# UI helper
# ----------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _data_loaded_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def render_refresh_button() -> None:
    """Sidebar button: drops every cached download/computation and reruns."""
    if st.sidebar.button("🔄 Canlı Verileri Yenile", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.caption(f"Veri yüklenme zamanı: {_data_loaded_at()} · otomatik yenileme: 15 dk")
