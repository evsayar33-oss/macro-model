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


def _toy_prices(n=900, seed=0):
    idx = pd.bdate_range("2021-01-04", periods=n)
    rng = np.random.default_rng(seed)
    vols = [0.009, 0.018, 0.016, 0.012, 0.035, 0.022, 0.015, 0.009]
    return idx, {a: pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0003, v, n))), idx)
                 for a, v in zip(m.ASSET_MARKET_TICKERS, vols)}


def test_min_drawdown_beats_equal_weight_in_sample_and_respects_caps():
    from regime_portfolio import compute_regime_portfolios, DEFAULT_CAP
    idx, prices = _toy_prices()
    regime = pd.Series(np.repeat([0, 1, 2, 0, 5, 1], 150)[: len(idx)], idx)
    out = compute_regime_portfolios(regime, prices)
    for rid, p in out["portfolios"].items():
        w = p["weights"]
        assert abs(sum(w.values()) - 1) < 1e-6 and max(w.values()) <= DEFAULT_CAP + 1e-6 and min(w.values()) >= -1e-9
        if p["stats"].get("days", 0) >= 60:
            assert p["stats"]["max_drawdown"] >= p["ew_stats"]["max_drawdown"] - 1e-9  # less negative


def test_active_target_sums_to_100_with_cash():
    from regime_portfolio import active_target_weights, compute_regime_portfolios, CASH_KEY
    idx, prices = _toy_prices()
    out = compute_regime_portfolios(pd.Series(0, idx), prices)
    tgt = active_target_weights(out, 0, 0, False, 0.4)
    assert abs(sum(tgt.values()) - 100) < 1e-6 and abs(tgt[CASH_KEY] - 60) < 1e-6


def test_all_strategies_sum_to_100_and_never_lever():
    from regime_portfolio import STRATEGY_LABELS, strategy_weights, CASH_KEY
    idx, prices = _toy_prices(n=900)
    reg = pd.Series(np.repeat([0, 1, 2], 300), idx)
    for s in STRATEGY_LABELS:
        w = strategy_weights(s, prices, reg, 1, 1, False)
        assert abs(sum(w.values()) - 100) < 1e-6 and w[CASH_KEY] >= -1e-6, s


def test_tlt_high_real_yield_is_supportive_value_factor():
    from asset_signal_engine import compute_factor_scores, REAL_YIELD_VALUE_NAME, REAL_YIELD_NAME
    idx = _bidx(900)
    s = pd.Series(np.r_[np.linspace(0.5, 2.85, 700), np.full(200, 2.85)], index=idx)  # high but now stable
    fs = compute_factor_scores({"dfii10": s})
    assert fs[REAL_YIELD_VALUE_NAME]["z"] > 1.0          # cheap bonds -> positive for TLT
    assert abs(fs[REAL_YIELD_NAME]["z"]) < 1.0            # no further rise -> no momentum penalty


def test_cycle_engine_sells_top_buys_bottom_and_holds():
    from cycle_engine import cycle_states
    idx = pd.bdate_range("2008-01-01", periods=4000)
    t = np.arange(len(idx))
    p = pd.Series(100 * np.exp(0.5 * np.sin(2 * np.pi * t / 900)), idx)      # clean multi-year cycle
    st = cycle_states(p, {"L": 504, "q_low": 0.15, "q_high": 0.85, "confirm": True, "reentry": "bottom"})
    sells = st[st["event"] == "SAT-UNUT"]; buys = st[st["event"] == "AL-UNUT"]
    assert len(sells) >= 2 and len(buys) >= 2
    # sells happen in the upper part of the cycle, buys in the lower part
    assert (np.sin(2 * np.pi * np.searchsorted(idx, sells.index) / 900) > 0).mean() > 0.7
    assert (np.sin(2 * np.pi * np.searchsorted(idx, buys.index) / 900) < 0).mean() > 0.7
    # "al-unut": far fewer position changes than days
    assert st["in_market"].diff().abs().sum() < 20


def test_bond_excluded_from_cycle_engine():
    from cycle_engine import current_cycle_signal
    out = current_cycle_signal("ABD Tahvili / Faiz (TLT)", pd.Series([1.0, 2.0]))
    assert out["applicable"] is False


def test_drawdown_brake_reduces_max_drawdown():
    from regime_portfolio import simulate_strategy, build_price_panel
    from cycle_engine import perf_stats
    idx, prices = _toy_prices(n=1500, seed=5)
    px = build_price_panel(prices)
    a = perf_stats(simulate_strategy("rp_vt|vol10", px)["returns"])
    b = perf_stats(simulate_strategy("rp_vt|regime_vol_ddbrake", px)["returns"])
    assert b["max_dd"] >= a["max_dd"] - 1e-9
