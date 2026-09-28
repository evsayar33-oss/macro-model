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
