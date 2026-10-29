"""
Williams %R Mean-Reversion Strategy
Based on: classic Williams %R (14) overbought/oversold reversal
Logic: %R measures where the close sits within the 14-bar high-low range.
       %R <= -80 means the close is in the bottom 20% of the range
       (oversold); %R >= -20 means the top 20% (overbought).
       Classic reversal: fade the extreme.
Entry: Open of the day AFTER the signal bar (the backtester handles
       next-bar-open execution; this module reports the signal bar).
Stop: 1.0 * ATR from entry (Wilder-smoothed 14-period ATR)
Target: middle of the 14-bar range (mean-reversion target)

NOTE: This is the strategy that the live scanner (us_live_scan.py) actually
uses to tag "%R Rev". The earlier repo file named `percent_r_mean_rev` was a
DIFFERENT strategy (daily-range percentile rank), despite the similar name.
"""

import numpy as np


def _atr(highs, lows, closes, n, p=14):
    """Wilder-smoothed ATR array."""
    at = np.full(n, np.nan)
    if n < p + 1:
        return at
    tr = [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1])) for i in range(1, n)]
    at[p] = sum(tr[:p]) / p
    for i in range(p + 1, n):
        at[i] = (at[i - 1] * (p - 1) + tr[i - 1]) / p
    return at


def detect(df):
    signals = []
    closes = df['Close'].values.astype(float)
    highs = df['High'].values.astype(float)
    lows = df['Low'].values.astype(float)
    n = len(closes)
    if n < 30:
        return signals

    at = _atr(highs, lows, closes, n, 14)

    # Williams %R over 14 bars
    wr = np.full(n, np.nan)
    p = 14
    for i in range(p - 1, n):
        hh = np.max(highs[i - p + 1:i + 1])
        ll = np.min(lows[i - p + 1:i + 1])
        if hh != ll:
            wr[i] = -100.0 * (hh - closes[i]) / (hh - ll)

    for i in range(p, n):
        if np.isnan(at[i]) or np.isnan(wr[i]):
            continue
        atrd = float(at[i])
        if atrd <= 0:
            continue

        hh = np.max(highs[i - p + 1:i + 1])
        ll = np.min(lows[i - p + 1:i + 1])
        mid = (hh + ll) / 2.0
        close = float(closes[i])

        # Oversold -> long (expect reversion toward the middle of the range)
        if wr[i] <= -80.0:
            entry = close
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'long',
                'entry': entry,
                'sl': round(entry - 1.0 * atrd, 4),
                'tp': round(mid, 4),
                'atr': atrd,
                'desc': f'Williams %R oversold: %R={wr[i]:.1f}, close near 14-bar low, fade to mid {mid:.2f}',
            })

        # Overbought -> short
        elif wr[i] >= -20.0:
            entry = close
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'short',
                'entry': entry,
                'sl': round(entry + 1.0 * atrd, 4),
                'tp': round(mid, 4),
                'atr': atrd,
                'desc': f'Williams %R overbought: %R={wr[i]:.1f}, close near 14-bar high, fade to mid {mid:.2f}',
            })

    return signals
