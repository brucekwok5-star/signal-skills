"""
Regression tests for the backtester and the strategies it drives.

These lock in the three bugs fixed on 2026-10-29, each of which silently
inflated avg R into fake edge:

  1. Partial in-progress bars (yfinance returns today's unfinished session).
  2. Stop/TP anchored to the signal day's open while the backtest enters at
     the NEXT day's open -- on a gap the stop lands at entry, risk -> 0 and
     R explodes (one SPY trade produced +537.83R).
  3. Exit computed from the EOD close even when the stop/target was touched
     intraday.

Run:  ~/.hermes/hermes-agent/venv/bin/python -m pytest tests/ -q
"""
import importlib.util
import json
import glob
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yfinance as yf

REPO = Path(__file__).resolve().parent.parent


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bt():
    return _load(REPO / "backtest_all.py", "bt_under_test")


@pytest.fixture(scope="module")
def wr():
    return _load(REPO / "strategies" / "williams_r_reversion.py", "wr_under_test")


def flat(n, o=100.0, h=105.0, l=95.0, c=100.0):
    return pd.DataFrame({
        "Open": np.full(n, o), "High": np.full(n, h),
        "Low": np.full(n, l), "Close": np.full(n, c),
        "Volume": np.full(n, 1e6),
    })


SIG = 20  # signal bar must be >= 14 for ATR to be defined
ONE = {"date": SIG, "direction": "long", "entry": 100.0, "sl": 98.0, "tp": 103.0, "atr": 5.0}


def run_backtest(bt, bars, signals):
    """Run the backtester over a single synthetic symbol."""
    orig_get, orig_univ = bt.get_bars, bt.US_UNIVERSE
    bt.US_UNIVERSE = ["TEST"]
    bt.get_bars = lambda s: bars
    try:
        return bt.backtest("t", lambda _d: [dict(s) for s in signals])
    finally:
        bt.get_bars, bt.US_UNIVERSE = orig_get, orig_univ


# ── strategy: williams_r_reversion ──────────────────────────────────────────

def test_detect_returns_wellformed_signals(wr):
    df = flat(60)
    for col in ("Open", "High", "Low", "Close"):
        df[col] = np.linspace(100, 140, 60)
    sigs = wr.detect(df)
    assert sigs, "expected signals on trending data"
    for s in sigs:
        assert s["direction"] in ("long", "short")
        assert {"date", "direction", "entry", "sl", "tp", "atr", "desc"} <= set(s)
        assert s["atr"] > 0
        if s["direction"] == "long":
            assert s["sl"] < s["entry"]
        else:
            assert s["sl"] > s["entry"]


def test_oversold_close_generates_long(wr):
    c = np.full(40, 100.0)
    df = pd.DataFrame({"Open": c, "High": np.full(40, 110.0), "Low": np.full(40, 90.0),
                       "Close": c, "Volume": np.full(40, 1e6)})
    df.loc[df.index[-1], "Close"] = 91.0        # pinned to bottom of range
    sigs = wr.detect(df)
    assert [s["direction"] for s in sigs] == ["long"]


def test_overbought_close_generates_short(wr):
    c = np.full(40, 100.0)
    df = pd.DataFrame({"Open": c, "High": np.full(40, 110.0), "Low": np.full(40, 90.0),
                       "Close": c, "Volume": np.full(40, 1e6)})
    df.loc[df.index[-1], "Close"] = 109.0       # pinned to top of range
    sigs = wr.detect(df)
    assert [s["direction"] for s in sigs] == ["short"]


def test_detect_needs_minimum_bars(wr):
    assert wr.detect(flat(10)) == []


# ── backtester bug 2: SL/TP re-anchored to the actual entry ─────────────────

def test_stop_is_reanchored_to_next_bar_open(bt):
    bars = flat(40)
    bars.iloc[SIG + 1, bars.columns.get_loc("Open")] = 120.0   # +20 gap
    bars.iloc[SIG + 1, bars.columns.get_loc("Close")] = 121.0
    bars.iloc[SIG + 1, bars.columns.get_loc("Low")] = 119.0
    bars.iloc[SIG + 1, bars.columns.get_loc("High")] = 122.0
    t = run_backtest(bt, bars, [ONE])["trades"][0]
    assert t["entry"] == pytest.approx(120.0)
    assert t["sl"] == pytest.approx(118.0)      # entry - 2, not the stale 98
    assert t["tp"] == pytest.approx(123.0)      # entry + 3
    assert abs(t["r"]) < 20                     # would have been ~537 before


def test_gap_does_not_explode_r(bt):
    """The +537.83R regression: risk collapsing to ~0 on a gap."""
    bars = flat(40)
    bars.iloc[SIG + 1, bars.columns.get_loc("Open")] = 120.0
    bars.iloc[SIG + 1, bars.columns.get_loc("Close")] = 130.0
    bars.iloc[SIG + 1, bars.columns.get_loc("Low")] = 119.0
    bars.iloc[SIG + 1, bars.columns.get_loc("High")] = 131.0
    t = run_backtest(bt, bars, [ONE])["trades"][0]
    assert abs(t["r"]) <= 5.0                   # hard cap


def test_degenerate_stop_at_entry_is_rejected(bt):
    bars = flat(40)
    bars.iloc[SIG + 1, bars.columns.get_loc("Low")] = 99.5
    bars.iloc[SIG + 1, bars.columns.get_loc("High")] = 100.5
    bad = {**ONE, "sl": 100.0}                  # stop exactly at entry
    assert run_backtest(bt, bars, [bad])["trades"] == []


# ── backtester bug 3: exit closes at SL/TP when touched ────────────────────

def test_stop_hit_closes_at_stop_not_eod(bt):
    bars = flat(40)
    bars.iloc[SIG + 1, bars.columns.get_loc("Low")] = 95.0     # stop 98 touched
    bars.iloc[SIG + 1, bars.columns.get_loc("High")] = 101.0   # EOD would read -2R
    t = run_backtest(bt, bars, [ONE])["trades"][0]
    assert t["hit_sl"] is True
    assert t["r"] == pytest.approx(-1.0)
    assert t["exit"] == pytest.approx(98.0)


def test_target_hit_closes_at_target(bt):
    bars = flat(40)
    bars.iloc[SIG + 1, bars.columns.get_loc("Low")] = 99.0     # stop not touched
    bars.iloc[SIG + 1, bars.columns.get_loc("High")] = 104.0   # target 103 touched
    t = run_backtest(bt, bars, [ONE])["trades"][0]
    assert t["hit_tp"] is True
    assert t["r"] == pytest.approx(1.5)


def test_untouched_trade_exits_at_eod_close(bt):
    bars = flat(40)
    bars.iloc[SIG + 1, bars.columns.get_loc("Open")] = 100.0
    bars.iloc[SIG + 1, bars.columns.get_loc("Close")] = 101.0
    bars.iloc[SIG + 1, bars.columns.get_loc("Low")] = 99.5
    bars.iloc[SIG + 1, bars.columns.get_loc("High")] = 101.5
    t = run_backtest(bt, bars, [ONE])["trades"][0]
    assert not t["hit_sl"] and not t["hit_tp"]
    assert t["r"] == pytest.approx(0.5)


# ── backtester bug 1: partial in-progress bar dropped ───────────────────────

class _FakeDate:
    def __init__(self, d):
        self.d = d

    def date(self):
        return self.d


def test_partial_bar_dropped_while_market_open(bt, monkeypatch):
    today = pd.Timestamp.now(tz="America/New_York").date()
    rows = [{"Date": _FakeDate(today if i == 24 else today - pd.Timedelta(days=i + 1)),
             "Open": 100.0, "High": 105.0, "Low": 95.0, "Close": 100.0, "Volume": 1e6}
            for i in range(25)]
    monkeypatch.setattr(yf.Ticker, "history", lambda self, *a, **k: pd.DataFrame(rows))
    monkeypatch.setattr(bt, "_market_open_now", lambda: True)
    bars = bt.get_bars("X")
    assert len(bars) == 24
    assert str(bars["Date"].iloc[-1].date()) != str(today)


def test_partial_bar_kept_after_close(bt, monkeypatch):
    today = pd.Timestamp.now(tz="America/New_York").date()
    rows = [{"Date": _FakeDate(today if i == 24 else today - pd.Timedelta(days=i + 1)),
             "Open": 100.0, "High": 105.0, "Low": 95.0, "Close": 100.0, "Volume": 1e6}
            for i in range(25)]
    monkeypatch.setattr(yf.Ticker, "history", lambda self, *a, **k: pd.DataFrame(rows))
    monkeypatch.setattr(bt, "_market_open_now", lambda: False)
    assert len(bt.get_bars("X")) == 25


def test_market_open_window(bt, monkeypatch):
    """Market is 'open' (partial bar pending) before 16:00 ET on a weekday."""
    from datetime import datetime, timedelta, timezone
    ny = timezone(timedelta(hours=-4))
    real_datetime = bt.datetime
    try:
        for hour, expect in ((10, True), (15, True), (16, False), (20, False)):
            fake = datetime(2026, 10, 28, hour, 0, tzinfo=ny)   # a Wednesday
            monkeypatch.setattr(bt, "datetime", type("D", (), {
                "now": staticmethod(lambda tz: fake),
                "timezone": staticmethod(lambda *a: tz),
            }))
            assert bt._market_open_now() is expect, f"{hour}:00 ET"
    finally:
        bt.datetime = real_datetime


# ── published results: distribution sanity ───────────────────────────────────

def _all_trades():
    out = []
    for f in glob.glob(str(REPO / "backtest_results" / "*.json")):
        out += json.load(open(f))["trades"]
    return out


def test_no_extreme_r_outliers():
    rs = np.array([t["r"] for t in _all_trades()])
    assert rs.size > 1000
    assert np.abs(rs).max() <= 5.01, f"max |R| = {np.abs(rs).max()}"


def test_r_distribution_is_not_outlier_driven():
    rs = np.array([t["r"] for t in _all_trades()])
    assert (np.abs(rs) > 10).sum() == 0
    assert abs(np.median(rs) - rs.mean()) < 0.15


def test_williams_r_reversion_passes_review_filter():
    c = json.load(open(REPO / "backtest_results" / "williams_r_reversion.json"))["combined"]
    assert c["n"] >= 10
    assert c["wr"] > 45
    assert c["avg_r"] > 0.05
