# Signal Skills

US-stock trading strategy research: strategy implementations, a backtester,
and a live scanner.

## Layout

```
strategies/          one .py per strategy, each exposing detect(df) -> [signals]
backtest_all.py      batch backtester over the 39-stock universe
us_live_scan.py      live scanner (Tencent qt.gtimg.cn quotes + yfinance history)
backtest_results/    per-strategy JSON (metrics + full trade list)
tests/               pytest regression suite
effective_strategies.md   ranked review + caveats
```

## Strategy contract

```python
def detect(df):
    """df has Open/High/Low/Close/Volume columns (yfinance casing).
    Returns [{date, direction, entry, sl, tp, atr, desc}, ...]
    direction: 'long' | 'short'
    """
```

The backtester enters at the **next** bar's open and exits at that bar's
close, or at the stop/target if touched intraday. R is normalised by the
actual stop distance.

## Commands

```bash
PY=~/.hermes/hermes-agent/venv/bin/python

$PY -m pytest tests/ -q          # regression suite (16 tests)
$PY backtest_all.py              # re-run every strategy, refresh backtest_results/
$PY us_live_scan.py              # live top-3 long / top-3 short
```

## Backtest integrity

Three bugs previously inflated `avg R` into fake edge. `tests/` locks all
three down, and `backtest_all.py` guards against them:

1. **Partial bars** — yfinance returns today's unfinished session intraday;
   it is dropped so an incomplete day is never treated as complete.
2. **Stop re-anchoring** — strategies anchor SL/TP to the signal day's open
   but the backtest enters at the *next* day's open. On a gap the stop lands
   at entry, `risk -> 0` and R explodes (one SPY trade produced +537.83R and
   carried an entire strategy's average). The stop is re-anchored to the
   actual entry, preserving its distance.
3. **Exit model** — if the stop or target was touched intraday the trade
   closes *at that level*, not at the EOD close.

Sanity checks on every result: max abs(R) < 10, and median R close to mean R.
A single trade with R in the hundreds is corruption, not edge.

## Current status

Only `williams_r_reversion` passes the review filter (avg R > 0.05,
WR > 45%, N >= 10) — and its edge is regime-dependent (holds over 60-90
days, flattens to ~0 over a year). `gap_fill` is **losing** despite being
tagged by the live scanner; treat those tags as informational.

See `effective_strategies.md` for the full ranking and caveats.
