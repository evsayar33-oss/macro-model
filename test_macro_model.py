"""Regression tests for the v2.4 fixes (run: python -m pytest -q)."""

import numpy as np
import pandas as pd

import macro_event_interpretation as m
from asset_signal_engine import INDICATOR_SPECS, compute_all_asset_signals, compute_factor_scores, process_indicator


def _bidx(n, start="2021-01-04"):
    return pd.date_range(start, periods=n, freq="B")


def test_real_yield_sign_is_not_double_inverted():
    idx = _bidx(600)
    fell = pd.Series(np.r_[np.full(580, 1.5), np.full(20, 0.2)], index=idx)
    rose = pd.Series(np.r_[np.full(580, 1.5), np.full(20, 2.8)], index=idx)
    inv = dict((n, i) for n, _k, i in INDICATOR_SPECS)["Reel Faiz İndirgeme İvmesi (10Y TIPS)"]
    name = "Reel Faiz İndirgeme İvmesi (10Y TIPS)"
    assert process_indicator(fell, name, inv)[0] > 0   # real yields falling -> supportive
    assert process_indicator(rose, name, inv)[0] < 0   # real yields rising -> adverse


def test_5y5y_reaches_level_anchor_branch():
    idx = _bidx(600)
    high = pd.Series(np.full(600, 2.9), index=idx)      # flat but high level
    z, _ = process_indicator(high, "5Y5Y İleri Enflasyon Beklentisi (T5YIFR)", False)
    assert z > 0.5   # generic EMA-trend branch would give ~0 for a flat series


def test_stale_regime_lapses_while_other_candidate_flickers():
    seq = [1] * 6 + [0, 5, 5, 0, 5] * 8
    it = iter(seq)
    sysm = m.MacroEventInterpretationSystem()
    idx = _bidx(len(seq))
    sysm.compute_indicators = lambda d: pd.DataFrame(index=idx)
    sysm.evaluate_row = lambda row: {"candidate_id": next(it), "candidate_name": "x", "subtype": "N/A",
                                      "conflict_note": "Yok", "extreme_event": False,
                                      "candidate_strength": 0.0, "details": {}}
    conf = sysm.evaluate_history({})["confirmed_regime_id"].tolist()
    stale_days = sum(1 for c, s in zip(conf[6:], seq[6:]) if c == 1)
    assert stale_days <= sysm.config.hysteresis_period_days


def test_dtwex_live_edge_is_nowcast_not_flat():
    idx = _bidx(700)
    rng = np.random.default_rng(1)
    dxy = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, 700)))
    dxy[-5:] = dxy[-6] * np.exp(np.cumsum(np.full(5, 0.004)))
    dt = 115 * np.exp(np.cumsum(0.65 * np.diff(np.log(dxy), prepend=np.log(dxy[0]))))
    data = {"dxy": pd.Series(dxy, idx), "dtwex": pd.Series(dt[:-5], idx[:-5])}
    f = m.MacroEventInterpretationSystem().compute_indicators(data)
    assert f["dtwex_nowcast_days"].iloc[-1] == 5
    assert f["dtwex_chg5_z"].iloc[-1] > 1.0


def test_shared_engine_produces_all_assets():
    idx = _bidx(800)
    rng = np.random.default_rng(2)
    series = {k: pd.Series(2 + np.cumsum(rng.normal(0, 0.01, 800)), idx) for _n, k, _i in INDICATOR_SPECS}
    fs = compute_factor_scores(series)
    prices = {a: pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 800))), idx) for a in m.ASSET_MARKET_TICKERS}
    out = compute_all_asset_signals({k: v["z"] for k, v in fs.items()}, prices,
                                    m.compute_structural_risk_state(None), 0, "N/A",
                                    {"GOLDILOCKS": 0.25, "REFLASYON": 0.25, "STAGFLASYON": 0.25, "DEFLASYON": 0.25}, False)
    assert len(out) == 8 and all(-100 <= v["score"] <= 100 for v in out.values())


def test_publication_lag_moves_dates_forward():
    from historical_validation import apply_publication_lag
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-01-03", "2026-01-10"]))  # Saturdays (ICSA)
    lagged = apply_publication_lag(s, 4)
    assert (lagged.index > s.index).all()
