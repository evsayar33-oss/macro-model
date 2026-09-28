"""
Long-Horizon Cycle Engine — "tepeden sat, dipten al" (al-unut / sat-unut)
==========================================================================
For every asset EXCEPT the bond (TLT, which follows the rate model), a slow,
low-turnover signal that sells into long-horizon overvaluation and buys into
long-horizon undervaluation, holds until the opposite extreme, uses no
leverage and no shorting ("sat" = exit to cash and wait).

How "top" and "bottom" are measured (all point-in-time, trailing only)
-----------------------------------------------------------------------
* value deviation  = log(price) − mean(log price over the last L days)
  (L = 2 or 3 years): how stretched the asset is versus its own multi-year
  trend. This is the long-horizon reversal / "value" signal that institutional
  cross-asset research finds in equities, commodities and currencies.
* value_z          = that deviation expressed in the asset's OWN historical
  units (expanding mean / std) -> comparable across years and assets.
* zones            = the asset's own EXPANDING quantiles of the deviation (e.g. the
  cheapest 15% / most expensive 15% of its history). No fixed magic number:
  the bands recalibrate themselves as history accumulates.
* setup + trigger  = touching a zone ARMS the signal for ~6 months; it fires
  when the turn is confirmed while price is still on that side of its median.
* confirmation     = optional "the knife has stopped falling" test: at a
  bottom, price back above its 50-day average and 20-day return > 0; at a
  top, below its 50-day average and 20-day return < 0.

State machine (persistent — this is what makes it "al-unut / sat-unut")
------------------------------------------------------------------------
  IN  --(top zone [+ confirmation])------------------------> OUT   "SAT-UNUT"
  OUT --(bottom zone [+ confirmation])---------------------> IN    "AL-UNUT"
  OUT --(re-entry mode "mean": value_z back below its median
         and price turning up)---------------------------> IN
Between signals the previous decision is simply held.

Which L / zone width / confirmation / re-entry rule each asset uses is NOT
chosen by hand: historical_validation.py runs a walk-forward race (yearly
re-selection using only past data, judged on the next year) and writes the
winner per asset to validation_reports/cycle_params.json. Until that file
exists, DEFAULT_PARAMS is used.
"""

from __future__ import annotations

import itertools
import json
import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

CYCLE_PARAMS_FILE = os.path.join("validation_reports", "cycle_params.json")
EXCLUDED_ASSETS = {"ABD Tahvili / Faiz (TLT)"}      # bonds follow the rate model
MIN_Z_HISTORY = 252
MIN_BAND_HISTORY = 504
ARM_DAYS = 120               # a top/bottom setup waits up to ~6 months for its turn confirmation        # ~2 years of deviation history before bands are trusted

DEFAULT_PARAMS = {"L": 756, "q_low": 0.15, "q_high": 0.85, "confirm": True, "reentry": "mean"}

PARAM_GRID = [
    {"L": L, "q_low": ql, "q_high": qh, "confirm": c, "reentry": r}
    for L, (ql, qh), c, r in itertools.product(
        (504, 756), ((0.10, 0.90), (0.15, 0.85), (0.20, 0.80)), (True, False), ("bottom", "mean"))
]


def _clean(price: pd.Series) -> pd.Series:
    s = pd.Series(price).dropna().astype(float)
    s.index = pd.to_datetime(s.index)
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s = s[s > 0]
    return s.resample("B").last().ffill().dropna()


def cycle_features(price: pd.Series, L: int) -> pd.DataFrame:
    s = _clean(price)
    lp = np.log(s)
    ma = lp.rolling(L, min_periods=L).mean()
    dev = lp - ma
    mu = dev.expanding(min_periods=MIN_Z_HISTORY).mean()
    sd = dev.expanding(min_periods=MIN_Z_HISTORY).std()
    z = (dev - mu) / sd.replace(0, np.nan)
    ma50 = s.rolling(50, min_periods=50).mean()
    r20 = s.pct_change(20)
    return pd.DataFrame({
        "price": s, "value_z": z, "dev": dev,
        "turn_up": (s > ma50) & (r20 > 0),
        "turn_down": (s < ma50) & (r20 < 0),
    })


def cycle_states(price: pd.Series, params: Dict[str, Any], feats: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Daily point-in-time states. Columns: value_z, lower, upper, zone, in_market (0/1), event."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    f = feats if feats is not None else cycle_features(price, int(p["L"]))
    # Bands are quantiles of the raw deviation itself (stable units), not of the
    # expanding z-score: z computed with still-maturing mean/std is inflated in
    # early history, which pinned the upper band too high to ever trigger.
    z = f["dev"]
    lower = z.expanding(min_periods=MIN_BAND_HISTORY).quantile(float(p["q_low"]))
    upper = z.expanding(min_periods=MIN_BAND_HISTORY).quantile(float(p["q_high"]))
    median = z.expanding(min_periods=MIN_BAND_HISTORY).median()
    zv, lo, hi, md = z.to_numpy(), lower.to_numpy(), upper.to_numpy(), median.to_numpy()
    tu, td = f["turn_up"].to_numpy(), f["turn_down"].to_numpy()
    confirm = bool(p["confirm"]); mean_reentry = p["reentry"] == "mean"
    n = len(f)
    state = np.ones(n, dtype=int)          # start invested (buy & hold until the first top)
    event = np.array([""] * n, dtype=object)
    zone = np.array(["NÖTR"] * n, dtype=object)
    cur = 1
    armed_top = armed_bot = 0              # "setup" stays armed ARM_DAYS after the zone was touched
    for i in range(n):
        if not (np.isfinite(zv[i]) and np.isfinite(lo[i]) and np.isfinite(hi[i])):
            state[i] = cur; continue
        if zv[i] >= hi[i]:
            zone[i] = "TEPE"; armed_top = ARM_DAYS; armed_bot = 0
        elif zv[i] <= lo[i]:
            zone[i] = "DİP"; armed_bot = ARM_DAYS; armed_top = 0
        above_mid = np.isfinite(md[i]) and zv[i] > md[i]
        below_mid = np.isfinite(md[i]) and zv[i] < md[i]
        if cur == 1 and armed_top > 0 and above_mid and (td[i] or (not confirm and zone[i] == "TEPE")):
            cur = 0; event[i] = "SAT-UNUT"; armed_top = 0
        elif cur == 0 and armed_bot > 0 and below_mid and (tu[i] or (not confirm and zone[i] == "DİP")):
            cur = 1; event[i] = "AL-UNUT"; armed_bot = 0
        elif cur == 0 and mean_reentry and armed_bot == 0 and np.isfinite(md[i]) and zv[i] <= md[i] and tu[i]:
            cur = 1; event[i] = "AL (ortalamaya dönüş)"
        armed_top = max(0, armed_top - 1); armed_bot = max(0, armed_bot - 1)
        state[i] = cur
    return pd.DataFrame({"value_z": f["value_z"], "dev": z, "lower": lower, "upper": upper, "zone": zone,
                         "in_market": state, "event": event, "price": f["price"]}, index=f.index)


def simulate_long_only(states: pd.DataFrame, cost_bps: float = 10.0) -> pd.Series:
    """Daily returns of holding the asset when in_market (decided at yesterday's close)."""
    ret = states["price"].pct_change().fillna(0.0)
    pos = states["in_market"].shift(1).fillna(1).astype(float)
    trades = pos.diff().abs().fillna(0.0)
    return pos * ret - trades * cost_bps / 1e4


def perf_stats(r: pd.Series) -> Dict[str, Optional[float]]:
    r = r.dropna()
    if len(r) < 60:
        return {"cagr": None, "max_dd": None, "calmar": None, "vol": None}
    cum = (1 + r).cumprod()
    yrs = len(r) / 252.0
    cagr = float(cum.iloc[-1] ** (1 / yrs) - 1)
    dd = float((cum / cum.cummax() - 1).min())
    vol = float(r.std() * np.sqrt(252))
    m = (1 + r).resample("ME").prod() - 1
    y = (1 + r).resample("YE").prod() - 1
    return {"cagr": cagr, "max_dd": dd, "calmar": cagr / abs(dd) if dd < 0 else None, "vol": vol,
            "sharpe": cagr / vol if vol > 0 else None,
            "win_month": float((m > 0).mean()) if len(m) else None,
            "win_year": float((y > 0).mean()) if len(y) else None}


def trade_stats(states: pd.DataFrame) -> Dict[str, Any]:
    """Round trips = entry (AL) -> exit (SAT). Win rate = share of profitable round trips;
    also the share of SAT signals followed by a lower price 120 days later."""
    px = states["price"]; pos = states["in_market"]
    changes = pos.diff().fillna(0)
    entries = list(px.index[changes > 0]); exits = list(px.index[changes < 0])
    trips = []
    for e in entries:
        x = next((t for t in exits if t > e), None)
        end_px = px.loc[x] if x is not None else px.iloc[-1]
        trips.append(float(end_px / px.loc[e] - 1))
    sell_ok = []
    for x in exits:
        loc = px.index.get_loc(x)
        if loc + 120 < len(px):
            sell_ok.append(float(px.iloc[loc + 120] < px.loc[x]))
    return {"round_trips": len(trips), "trip_win_rate": float(np.mean([t > 0 for t in trips])) if trips else None,
            "avg_trip_return": float(np.mean(trips)) if trips else None,
            "sell_signals": len(exits), "sell_hit_rate_120d": float(np.mean(sell_ok)) if sell_ok else None,
            "time_in_market": float(pos.mean())}


def _score(stats: Dict[str, Any]) -> float:
    c = stats.get("calmar")
    return -9.0 if c is None else float(c)


def walk_forward_select(price: pd.Series, first_train_years: int = 5, refit_days: int = 252) -> Dict[str, Any]:
    """Yearly re-selection of params on PAST data only; the chosen params trade the
    NEXT year. Returns the stitched out-of-sample return path + final selection."""
    s = _clean(price)
    feats = {L: cycle_features(s, L) for L in sorted({p["L"] for p in PARAM_GRID})}
    all_states = {i: cycle_states(s, p, feats[p["L"]]) for i, p in enumerate(PARAM_GRID)}
    all_rets = {i: simulate_long_only(st) for i, st in all_states.items()}
    idx = s.index
    start = first_train_years * 252
    if len(idx) <= start + 60:
        best = max(all_rets, key=lambda i: _score(perf_stats(all_rets[i])))
        return {"params": PARAM_GRID[best], "oos_returns": pd.Series(dtype=float), "selections": []}
    oos_parts: List[pd.Series] = []
    selections = []
    default_i = PARAM_GRID.index(DEFAULT_PARAMS) if DEFAULT_PARAMS in PARAM_GRID else 0
    # before the first selection the a-priori DEFAULT (not fitted) states apply
    oos_in = all_states[default_i]["in_market"].copy()
    t = start
    chosen = None
    while t < len(idx):
        train_end = idx[t - 1]
        chosen = max(all_rets, key=lambda i: _score(perf_stats(all_rets[i][all_rets[i].index <= train_end])))
        seg_end = idx[min(t + refit_days, len(idx)) - 1]
        mask = (all_rets[chosen].index > train_end) & (all_rets[chosen].index <= seg_end)
        oos_parts.append(all_rets[chosen][mask])
        oos_in[mask] = all_states[chosen]["in_market"][mask]
        selections.append({"from": str(train_end.date()), "params": PARAM_GRID[chosen]})
        t += refit_days
    final = max(all_rets, key=lambda i: _score(perf_stats(all_rets[i])))
    oos = pd.concat(oos_parts) if oos_parts else pd.Series(dtype=float)
    return {"params": PARAM_GRID[final], "oos_returns": oos, "selections": selections,
            "final_states": all_states[final], "oos_in_market": oos_in,
            "oos_start": oos.index[0] if len(oos) else None, "price": s}


def load_cycle_params(path: str = CYCLE_PARAMS_FILE) -> Dict[str, Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return {a: v.get("params", DEFAULT_PARAMS) for a, v in json.load(fh).get("assets", {}).items()}
    except Exception:
        return {}


def current_cycle_signal(asset: str, price: pd.Series, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Live, human-readable long-horizon signal for one asset."""
    if asset in EXCLUDED_ASSETS:
        return {"asset": asset, "applicable": False,
                "label": "— (tahvil: faiz modeli)", "reason": "Tahvil döngü motoru dışında; faiz/makro modeli geçerli."}
    p = params or load_cycle_params().get(asset) or DEFAULT_PARAMS
    try:
        st = cycle_states(price, p)
    except Exception as exc:
        return {"asset": asset, "applicable": True, "label": "VERİ YETERSİZ", "reason": str(exc)}
    st = st.dropna(subset=["dev"])
    if st.empty:
        return {"asset": asset, "applicable": True, "label": "VERİ YETERSİZ", "reason": "yetersiz geçmiş"}
    last = st.iloc[-1]
    ev = st[st["event"] != ""]
    last_ev = ev.iloc[-1] if len(ev) else None
    inm = int(last["in_market"])
    zone = str(last["zone"])
    if inm == 1 and zone == "TEPE":
        label = "⚠️ TEPE BÖLGESİ — satış teyidi bekleniyor (TUT)"
    elif inm == 0 and zone == "DİP":
        label = "🟡 DİP BÖLGESİ — dönüş teyidi bekleniyor (NAKİTTE BEKLE)"
    elif inm == 1:
        label = "🟢 AL-UNUT / TUT"
    else:
        label = "🔴 SAT-UNUT / NAKİTTE BEKLE"
    rng = float(last["upper"] - last["lower"]) if np.isfinite(last["upper"] - last["lower"]) else np.nan
    pos = float((last["dev"] - last["lower"]) / rng) if rng and np.isfinite(rng) and rng > 0 else np.nan
    return {
        "asset": asset, "applicable": True, "label": label, "in_market": inm, "zone": zone,
        "value_z": float(last["value_z"]), "lower": float(last["lower"]), "upper": float(last["upper"]),
        "band_position": pos,   # 0 = bottom band, 1 = top band
        "last_event": None if last_ev is None else str(last_ev["event"]),
        "last_event_date": None if last_ev is None else str(ev.index[-1].date()),
        "last_event_price": None if last_ev is None else float(last_ev["price"]),
        "params": p,
    }
