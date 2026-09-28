"""
Regime Minimum-Drawdown Portfolios
===================================
For every macro regime (0..5) the portfolio that historically suffered the
SMALLEST drawdowns while that regime was in force.

Method (institutional drawdown-risk optimisation, Chekhlov-Uryasev-Zabarankin):
  * Take the daily returns of the 8 assets on the days the engine had that
    regime CONFIRMED, and chain them into one "regime stress path".
  * Solve a linear program that minimises
        0.5 * MaxDD  +  0.5 * CDaR(95%)
    of that path. MaxDD is the single worst peak-to-trough fall (what was
    asked for); CDaR(95%) is the average of the worst 5% drawdown states,
    which keeps the answer from being tuned to one single historical episode.
  * Constraints: long-only, fully invested inside the risky basket, at most
    `cap` (35%) in any one asset, and a return floor: the portfolio's mean
    return in that regime must be at least half of the equal-weight basket's
    (or >= 0), so "minimum drawdown" cannot collapse into "hold only the
    least volatile asset whatever it earns". Equal weight always satisfies
    the constraints, so the problem is always feasible.
  * Regimes with little history are shrunk toward the all-days solution in
    proportion to their sample size (no over-fitting to a handful of days).

The live target = regime portfolio (blended with the candidate regime while
a transition is pending) x the structural risk budget; the rest is cash.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

REGIME_IDS = (0, 1, 2, 3, 4, 5)
CASH_KEY = "Nakit / Likit Rezerv"
MIN_REGIME_DAYS = 60          # below this, shrink toward the all-days portfolio
DEFAULT_CAP = 0.35
DEFAULT_ALPHA = 0.95


def _max_drawdown(path_returns: np.ndarray) -> float:
    if len(path_returns) == 0:
        return 0.0
    cum = np.cumprod(1.0 + path_returns)
    peak = np.maximum.accumulate(np.r_[1.0, cum])[1:]
    return float(np.min(cum / peak - 1.0))


def _cdar(path_returns: np.ndarray, alpha: float) -> float:
    if len(path_returns) == 0:
        return 0.0
    cum = np.cumprod(1.0 + path_returns)
    peak = np.maximum.accumulate(np.r_[1.0, cum])[1:]
    dd = 1.0 - cum / peak
    k = max(1, int(np.ceil((1.0 - alpha) * len(dd))))
    return float(-np.mean(np.sort(dd)[-k:]))


def optimise_min_drawdown(returns: pd.DataFrame, cap: float = DEFAULT_CAP, alpha: float = DEFAULT_ALPHA,
                          w_maxdd: float = 0.5) -> Optional[np.ndarray]:
    """LP on uncompounded cumulative returns (standard, convex formulation).
    Variables: w (n), u (T running peaks), M (max DD), zeta, z (T)."""
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix

    R = returns.to_numpy(dtype=float)
    T, n = R.shape
    if T < 5 or n == 0:
        return None
    C = np.cumsum(R, axis=0)                      # C[t] . w = cumulative return at t
    iw, iu, iM, iz0, izz = 0, n, n + T, n + T + 1, n + T + 2
    nv = n + T + 1 + 1 + T
    cost = np.zeros(nv)
    cost[iM] = w_maxdd
    cost[iz0] = (1 - w_maxdd)
    cost[izz:izz + T] = (1 - w_maxdd) / ((1 - alpha) * T)

    rows = 4 * T + 1
    A = lil_matrix((rows, nv))
    b = np.zeros(rows)
    r = 0
    for t in range(T):
        # u_t >= C_t w          ->  C_t w - u_t <= 0
        A[r, iw:iw + n] = C[t]; A[r, iu + t] = -1.0; r += 1
        # u_t >= u_{t-1}        ->  u_{t-1} - u_t <= 0
        if t > 0:
            A[r, iu + t - 1] = 1.0; A[r, iu + t] = -1.0; r += 1
        # M >= u_t - C_t w      ->  u_t - C_t w - M <= 0
        A[r, iu + t] = 1.0; A[r, iw:iw + n] = -C[t]; A[r, iM] = -1.0; r += 1
        # z_t >= u_t - C_t w - zeta
        A[r, iu + t] = 1.0; A[r, iw:iw + n] = -C[t]; A[r, iz0] = -1.0; A[r, izz + t] = -1.0; r += 1
    # return floor: mean(R w) >= floor
    mu = R.mean(axis=0)
    ew = float(mu.mean())
    floor = 0.5 * ew if ew > 0 else ew            # equal weight always satisfies it
    A[r, iw:iw + n] = -mu; b[r] = -floor; r += 1
    A = A[:r].tocsr(); b = b[:r]

    A_eq = np.zeros((1, nv)); A_eq[0, iw:iw + n] = 1.0
    bounds = [(0.0, cap)] * n + [(0.0, None)] * T + [(0.0, None), (None, None)] + [(0.0, None)] * T
    res = linprog(cost, A_ub=A, b_ub=b, A_eq=A_eq, b_eq=[1.0], bounds=bounds, method="highs")
    if not res.success:
        return None
    w = np.clip(res.x[iw:iw + n], 0.0, None)
    return w / w.sum() if w.sum() > 0 else None


def _stats(path: pd.Series, alpha: float) -> Dict[str, float]:
    r = path.to_numpy(dtype=float)
    return {
        "days": int(len(r)),
        "ann_return": float(np.mean(r) * 252) if len(r) else 0.0,
        "ann_vol": float(np.std(r) * np.sqrt(252)) if len(r) > 1 else 0.0,
        "max_drawdown": _max_drawdown(r),
        "cdar95": _cdar(r, alpha),
    }


def compute_regime_portfolios(
    confirmed_regime: pd.Series,
    asset_prices: Dict[str, pd.Series],
    lookback_days: int = 2500,
    cap: float = DEFAULT_CAP,
    alpha: float = DEFAULT_ALPHA,
    as_of=None,
) -> Dict[str, Any]:
    """Returns {"assets": [...], "portfolios": {regime_id: {...}}, "all": {...}}.
    Uses only data up to ``as_of`` (point-in-time safe for validation)."""
    prices = pd.DataFrame({a: s for a, s in asset_prices.items() if s is not None and len(s) > 30})
    if prices.empty:
        return {"assets": [], "portfolios": {}, "all": {}}
    prices = prices.sort_index()
    prices.index = pd.to_datetime(prices.index)
    if getattr(prices.index, "tz", None) is not None:
        prices.index = prices.index.tz_localize(None)
    prices = prices.resample("B").last().ffill()
    if as_of is not None:
        prices = prices[prices.index <= pd.Timestamp(as_of)]
    prices = prices[prices.index >= prices.index.max() - pd.Timedelta(days=lookback_days)]
    rets = prices.pct_change().dropna(how="all").fillna(0.0).clip(-0.5, 0.5)
    regime = confirmed_regime.copy()
    regime.index = pd.to_datetime(regime.index)
    regime = regime.reindex(rets.index, method="ffill").fillna(0).astype(int)
    # the regime known at the CLOSE of day t-1 governs the return of day t
    regime = regime.shift(1).fillna(0).astype(int)
    assets = list(rets.columns)
    n = len(assets)
    ew = np.full(n, 1.0 / n)

    w_all = optimise_min_drawdown(rets, cap, alpha)
    if w_all is None:
        w_all = ew
    out: Dict[str, Any] = {"assets": assets, "portfolios": {}}
    out["all"] = {
        "weights": dict(zip(assets, map(float, w_all))),
        "stats": _stats(rets @ w_all, alpha), "ew_stats": _stats(rets @ ew, alpha),
    }
    for rid in REGIME_IDS:
        sub = rets[regime == rid]
        days = len(sub)
        w_reg = optimise_min_drawdown(sub, cap, alpha) if days >= 20 else None
        trust = min(1.0, days / MIN_REGIME_DAYS)
        if w_reg is None:
            w, trust = w_all, 0.0
        else:
            w = trust * w_reg + (1.0 - trust) * w_all
            w = w / w.sum()
        out["portfolios"][rid] = {
            "weights": dict(zip(assets, map(float, w))),
            "trust": float(trust),
            "stats": _stats(sub @ w, alpha) if days else {"days": 0},
            "ew_stats": _stats(sub @ ew, alpha) if days else {"days": 0},
        }
    return out


def active_target_weights(
    regime_portfolios: Dict[str, Any],
    confirmed_regime_id: int,
    candidate_regime_id: int,
    in_transition: bool,
    risk_budget: float,
) -> Dict[str, float]:
    """Live target in percent: regime min-DD portfolio x risk budget, rest cash.
    While a different candidate is pending, 60% confirmed / 40% candidate."""
    ports = regime_portfolios.get("portfolios", {})
    assets = regime_portfolios.get("assets", [])
    if not assets:
        return {CASH_KEY: 100.0}
    base = ports.get(int(confirmed_regime_id)) or ports.get(0) or {"weights": {a: 1 / len(assets) for a in assets}}
    w = dict(base["weights"])
    if in_transition and candidate_regime_id != confirmed_regime_id and int(candidate_regime_id) in ports:
        cw = ports[int(candidate_regime_id)]["weights"]
        w = {a: 0.6 * w.get(a, 0.0) + 0.4 * cw.get(a, 0.0) for a in assets}
    budget = float(np.clip(risk_budget, 0.10, 0.90))
    out = {a: float(w.get(a, 0.0) * budget * 100.0) for a in assets}
    out[CASH_KEY] = float(100.0 - sum(out.values()))
    return out


# ======================================================================
# v2.6 — PORTFOLIO STRATEGY SET (evaluated out-of-sample, best one is live)
# ======================================================================
# Why: min-drawdown with a weak return floor, then scaled by the structural
# risk budget (avg ~56% cash), gives low drawdowns but weak returns. The
# strategies below are standard institutional answers to "better return per
# unit of drawdown". Every one of them is back-tested OUT-OF-SAMPLE in
# historical_validation.py; the live page uses the one with the best
# out-of-sample Calmar ratio (CAGR / |MaxDD|) from the latest report.

import json as _json
import os as _os

TARGET_VOL = 0.10            # annual portfolio volatility target
VOL_LOOKBACK = 60            # days for volatility / covariance
TREND_LOOKBACK = 200         # days for the trend filter
REGIME_DD_LIMIT = 0.10       # max drawdown allowed on a regime path (Calmar strategy)
STRATEGY_FILE = _os.path.join("validation_reports", "strategy_scores.json")

STRATEGY_LABELS = {
    "regime_calmar": "Rejim Calmar (rejimde maks. getiri, maks. DD ≤ %10) + vol hedefi",
    "risk_parity_vt": "Risk paritesi + %10 volatilite hedefi (düşeni alarak dengeler)",
    "risk_parity_trend": "Risk paritesi + 200g trend filtresi + %10 vol hedefi",
    "regime_min_dd": "Rejim minimum drawdown + %10 vol hedefi",
}
DEFAULT_STRATEGY = "risk_parity_vt"


def optimise_max_return_dd_limit(returns: pd.DataFrame, dd_limit: float = REGIME_DD_LIMIT,
                                 cap: float = DEFAULT_CAP) -> Optional[np.ndarray]:
    """Maximise mean return subject to MaxDD(path) <= dd_limit (LP, uncompounded)."""
    from scipy.optimize import linprog
    from scipy.sparse import lil_matrix
    R = returns.to_numpy(dtype=float)
    T, n = R.shape
    if T < 20 or n == 0:
        return None
    C = np.cumsum(R, axis=0)
    nv = n + T
    cost = np.zeros(nv); cost[:n] = -R.mean(axis=0)
    A = lil_matrix((3 * T, nv)); b = np.zeros(3 * T); r = 0
    for t in range(T):
        A[r, :n] = C[t]; A[r, n + t] = -1.0; r += 1                     # u_t >= C_t w
        if t > 0:
            A[r, n + t - 1] = 1.0; A[r, n + t] = -1.0; r += 1           # u_t >= u_{t-1}
        A[r, n + t] = 1.0; A[r, :n] = -C[t]; b[r] = dd_limit; r += 1     # u_t - C_t w <= limit
    A_eq = np.zeros((1, nv)); A_eq[0, :n] = 1.0
    bounds = [(0.0, cap)] * n + [(0.0, None)] * T
    res = linprog(cost, A_ub=A[:r].tocsr(), b_ub=b[:r], A_eq=A_eq, b_eq=[1.0], bounds=bounds, method="highs")
    if not res.success:
        return None
    w = np.clip(res.x[:n], 0, None)
    return w / w.sum() if w.sum() > 0 else None


def _clean_prices(asset_prices: Dict[str, pd.Series], as_of=None, lookback_days: int = 2500) -> pd.DataFrame:
    px = pd.DataFrame({a: s for a, s in asset_prices.items() if s is not None and len(s) > 30}).sort_index()
    px.index = pd.to_datetime(px.index)
    if getattr(px.index, "tz", None) is not None:
        px.index = px.index.tz_localize(None)
    px = px.resample("B").last().ffill()
    if as_of is not None:
        px = px[px.index <= pd.Timestamp(as_of)]
    return px[px.index >= px.index.max() - pd.Timedelta(days=lookback_days)]


def _vol_target_scale(weights: np.ndarray, rets: pd.DataFrame, target: float = TARGET_VOL) -> float:
    cov = rets.tail(VOL_LOOKBACK).cov().to_numpy() * 252
    vol = float(np.sqrt(max(weights @ cov @ weights, 1e-12)))
    return float(np.clip(target / vol, 0.0, 1.0))      # never levered, rest = cash


def _inverse_vol(rets: pd.DataFrame, cap: float = DEFAULT_CAP) -> np.ndarray:
    vol = rets.tail(VOL_LOOKBACK).std().to_numpy() * np.sqrt(252)
    inv = 1.0 / np.maximum(vol, 1e-4)
    w = inv / inv.sum()
    for _ in range(10):                                   # enforce cap, redistribute
        over = w > cap
        if not over.any():
            break
        excess = (w[over] - cap).sum(); w[over] = cap
        w[~over] += excess * w[~over] / w[~over].sum()
    return w


def strategy_weights(strategy: str, asset_prices: Dict[str, pd.Series], confirmed_regime: Optional[pd.Series] = None,
                     confirmed_id: int = 0, candidate_id: int = 0, in_transition: bool = False,
                     as_of=None, regime_cache: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """Target weights in percent (incl. cash) for one strategy, using data <= as_of only."""
    px = _clean_prices(asset_prices, as_of)
    rets = px.pct_change().dropna(how="all").fillna(0.0).clip(-0.5, 0.5)
    assets = list(px.columns)
    if len(rets) < TREND_LOOKBACK:
        return {CASH_KEY: 100.0}
    if strategy in ("risk_parity_vt", "risk_parity_trend"):
        w = _inverse_vol(rets)
        if strategy == "risk_parity_trend":
            above = (px.iloc[-1] > px.tail(TREND_LOOKBACK).mean()).to_numpy()
            w = np.where(above, w, 0.0)                  # filtered-out share goes to cash
        base = w
    else:
        cache = regime_cache if regime_cache is not None else {}
        key = f"{strategy}"
        if key not in cache:
            if strategy == "regime_min_dd":
                cache[key] = compute_regime_portfolios(confirmed_regime, asset_prices, as_of=as_of)
            else:
                cache[key] = compute_regime_calmar_portfolios(confirmed_regime, asset_prices, as_of=as_of)
        ports = cache[key]["portfolios"]
        wd = dict((ports.get(int(confirmed_id)) or ports.get(0) or {"weights": {a: 1 / len(assets) for a in assets}})["weights"])
        if in_transition and candidate_id != confirmed_id and int(candidate_id) in ports:
            cw = ports[int(candidate_id)]["weights"]
            wd = {a: 0.6 * wd.get(a, 0) + 0.4 * cw.get(a, 0) for a in assets}
        base = np.array([wd.get(a, 0.0) for a in assets])
    scale = _vol_target_scale(base, rets) if base.sum() > 0 else 0.0
    out = {a: float(base[i] * scale * 100.0) for i, a in enumerate(assets)}
    out[CASH_KEY] = float(100.0 - sum(out.values()))
    return out


def compute_regime_calmar_portfolios(confirmed_regime: pd.Series, asset_prices: Dict[str, pd.Series],
                                     lookback_days: int = 2500, cap: float = DEFAULT_CAP, as_of=None) -> Dict[str, Any]:
    """Per regime: maximum return subject to MaxDD <= REGIME_DD_LIMIT on that regime's path;
    falls back to the min-drawdown portfolio when the limit is infeasible."""
    base = compute_regime_portfolios(confirmed_regime, asset_prices, lookback_days, cap, as_of=as_of)
    px = _clean_prices(asset_prices, as_of, lookback_days)
    rets = px.pct_change().dropna(how="all").fillna(0.0).clip(-0.5, 0.5)
    reg = confirmed_regime.copy(); reg.index = pd.to_datetime(reg.index)
    reg = reg.reindex(rets.index, method="ffill").fillna(0).astype(int).shift(1).fillna(0).astype(int)
    assets = list(rets.columns)
    w_all = optimise_max_return_dd_limit(rets, dd_limit=0.25, cap=cap)
    for rid, p in base["portfolios"].items():
        sub = rets[reg == rid]
        w = optimise_max_return_dd_limit(sub, cap=cap) if len(sub) >= 60 else None
        if w is None:
            w = w_all if (w_all is not None and len(sub) < 60) else np.array([p["weights"][a] for a in assets])
        trust = min(1.0, len(sub) / MIN_REGIME_DAYS)
        if w_all is not None:
            w = trust * w + (1 - trust) * w_all
        p["weights"] = dict(zip(assets, map(float, w / w.sum())))
        if len(sub):
            p["stats"] = _stats(sub @ (w / w.sum()), DEFAULT_ALPHA)
    return base


def load_strategy_scores(path: str = STRATEGY_FILE) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return _json.load(fh)
    except Exception:
        return {}


def selected_strategy(path: str = STRATEGY_FILE) -> str:
    """Best out-of-sample Calmar from the latest validation run (self-improving
    selection); DEFAULT_STRATEGY until a validation run has produced scores."""
    scores = load_strategy_scores(path).get("strategies", {})
    valid = {k: v for k, v in scores.items() if k in STRATEGY_LABELS and v.get("calmar") is not None}
    if not valid:
        return DEFAULT_STRATEGY
    return max(valid, key=lambda k: valid[k]["calmar"])
