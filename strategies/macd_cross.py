"""
MACD Histogram Crossover Strategy
Entry: MACD histogram crosses above zero (bullish) or below zero (bearish)
Exit: EOD close
Stop: Entry +/- 2*ATR
"""

import numpy as np

def detect(df):
    signals = []
    closes = df['Close'].values
    highs  = df['High'].values
    lows   = df['Low'].values
    n = len(closes)
    if n < 26:
        return signals

    # MACD(12,26,9)
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd  = ema12 - ema26
    signal_line = _ema(macd, 9)
    histogram   = macd - signal_line

    for i in range(26, n):
        atrd = _atr(highs, lows, closes, i, 14)
        if atrd is None:
            continue

        prev_h = histogram[i-1]
        curr_h = histogram[i]

        entry = closes[i]

        # LONG: histogram crosses above zero
        if prev_h <= 0 and curr_h > 0:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'long',
                'entry': entry,
                'sl': round(entry - 2 * atrd, 2),
                'tp': round(entry + 3 * atrd, 2),
                'atr': atrd,
                'desc': 'MACD histogram crosses above zero'
            })

        # SHORT: histogram crosses below zero
        elif prev_h >= 0 and curr_h < 0:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'short',
                'entry': entry,
                'sl': round(entry + 2 * atrd, 2),
                'tp': round(entry - 3 * atrd, 2),
                'atr': atrd,
                'desc': 'MACD histogram crosses below zero'
            })

    return signals


def _ema(s, p):
    """Exponential moving average; skips leading NaNs in input array."""
    n = len(s)
    r = np.full(n, np.nan)
    # Find first window of p consecutive non-NaN values
    for start in range(n - p + 1):
        window = s[start:start + p]
        if not np.any(np.isnan(window)):
            r[start + p - 1] = np.mean(window)
            k = 2 / (p + 1)
            for i in range(start + p, n):
                r[i] = s[i] * k + r[i - 1] * (1 - k)
            return r
    return r


def _atr(h, l, c, idx, p=14):
    if idx < p:
        return None
    trs = []
    for j in range(idx - p + 1, idx + 1):
        tr = max(h[j] - l[j], abs(h[j] - c[j-1]) if j > 0 else h[j] - l[j], abs(l[j] - c[j-1]) if j > 0 else h[j] - l[j])
        trs.append(tr)
    if len(trs) < p:
        return None
    r = trs[0]
    for k in range(1, p):
        r = (r * (p - 1) + trs[k]) / p
    return r
