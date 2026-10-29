# Effective Strategies — Review (2026-10-29)

**Backtest protocol:** 39 US stocks, 90 trading days, signal observed at close,
entry at next trading day's open, exit at that day's close (or at the
stop/target if touched intraday). R normalized by actual stop distance.
Partial in-progress bars are excluded.

**Qualification filter:** avg R > 0.05, win rate > 45%, N >= 10.

## Ranked results

| Rank | Strategy | N | WR | Avg R | PF | Verdict |
|-----:|:---------|--:|---:|------:|--:|:--------|
| 1 | **williams_r_reversion** | 1353 | 54.6% | **+0.052R** | 1.281 | ✅ PASS |
| 2 | short_squeeze | 7 | 57.1% | +0.049R | 1.373 | ❌ N too small |
| 3 | volatility_breakout | 6 | 83.3% | +0.290R | 28.897 | ❌ N too small |
| 4 | bollinger_mean_rev | 113 | 52.2% | +0.011R | 1.234 | ⚠️ Below threshold |
| 5 | vwap_reversal | 1719 | 51.5% | +0.007R | 1.064 | ⚠️ Below threshold |
| 6 | rsi_momentum | 277 | 49.1% | −0.008R | 0.919 | ❌ Negative |
| 7 | adx_trend_follow | 49 | 46.9% | −0.010R | 0.906 | ❌ Negative |
| 8 | turtle_trading | 170 | 44.7% | −0.018R | 0.866 | ❌ Negative |
| 9 | macd_cross | 170 | 41.8% | −0.019R | 0.848 | ❌ Negative |
| 10 | donchian_breakout | 309 | 48.5% | −0.004R | 0.964 | ❌ Negative |
| 11 | rsi2_mean_rev | 791 | 44.2% | −0.042R | 0.669 | ❌ Negative |
| 12 | percent_r_mean_rev | 328 | 41.8% | −0.283R | 0.458 | ❌ Reject |
| 13 | **gap_fill** | 1545 | 14.5% | **−0.410R** | 0.518 | ❌ Reject |

## Only one strategy passes: Williams %R Reversion

`williams_r_reversion` is the only strategy meeting all three criteria
(avg R +0.052R > 0.05, WR 54.6% > 45%, N=1353 >= 10).

**Robustness across lookback windows:**

| Window | N | WR | Avg R | PF |
|:-------|--:|---:|------:|--:|
| 60d | 821 | 54.7% | +0.066R | 1.344 |
| 90d | 1353 | 54.6% | +0.052R | 1.281 |
| 180d | 3068 | 49.3% | −0.005R | 0.978 |
| 365d | 6477 | 49.9% | +0.004R | 1.015 |

**Honest read:** the edge is real but **regime-dependent**. It holds over 60-90
days and flattens to ~zero over 6-12 months. Treat it as a short-horizon
mean-reversion edge, not a structural long-term one. The 365d number (+0.004R)
is essentially breakeven — do not overstate the +0.052R figure.

## Important correction — prior results were corrupted

Earlier versions of this file reported `gap_fill` at +0.79R and
`percent_r_mean_rev` at +1.77R as the top strategies. **Both were wrong**, and
the causes were real bugs in the backtester, not market changes:

1. **Partial-bar contamination.** `get_bars()` returned yfinance's
   in-progress bar for the current session, so the most recent trade treated
   an unfinished day as a completed session.
2. **Stop not re-anchored to the actual entry.** Strategies compute their stop
   relative to the *signal day's* open, but the backtester enters at the *next*
   day's open. On a gap, the stop landed at or next to the entry price, making
   risk ≈ 0 and R explode. A single SPY trade produced **+537.83R** and carried
   the entire `percent_r_mean_rev` average (+1.773R → −0.186R once removed).
3. **Exit ignored stop/target hits.** R was always computed from the EOD close
   even when the stop or target had been touched intraday, distorting the
   whole R distribution.
4. **No outlier guard.** A single trade could dominate a strategy's mean.

`gap_fill`'s true performance is **−0.410R with a 14.5% win rate** — its
fixed 0.5% stop is hit on 84.9% of trades. The prior +0.79R was an artifact.

**Implication for live trading:** the live scanner (`us_live_scan.py`) tags
`Gap Fill` signals, but that strategy is now shown to be **losing money** in a
realistic exit model. Treat Gap Fill signals as informational only.

## Live scanner tag mapping

| Scanner tag | Backtested strategy | Status |
|:------------|:-------------------|:-------|
| `%R Rev` | `williams_r_reversion` | ✅ Passes |
| `Gap Fill` | `gap_fill` | ❌ Negative expectancy |
| `Vol Break` | `volatility_breakout` | ⚠️ N=6, unproven |

## Short side

Across the whole repo the short side remains negative or unproven. The best
short reading is `adx_trend_follow` short at +0.043R (N=25) — well below the
N>=10 threshold for that side, and the overall historical US short expectancy
remains negative. **Short signals should be watchlist-only, not deployed.**
