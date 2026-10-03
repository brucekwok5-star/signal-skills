"""
RSI(2) Mean-Reversion Strategy
Entry: RSI(2) crosses below 10 (extremely oversold) -> long
Exit: EOD close
Stop: Entry - 2*ATR
"""

import numpy as np

def detect(df):
    signals = []
    closes = df['close'].values
    highs  = df['high'].values
    lows   = df['low'].values
    n = len(closes)
    if n < 3:
        return signals

    # RSI(2)
    rsis = _rsi2(closes)

    for i in range(2, n):
        atrd = _atr(highs, lows, closes, i, 14)
        if atrd is None:
            continue

        prev_rsi = rsis[i-1]
        curr_rsi = rsis[i]
        entry = closes[i]

        # LONG: RSI(2) crosses below 10 (extremely oversold)
        if prev_rsi >= 10 and curr_rsi < 10:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'long',
                'entry': entry,
                'sl': round(entry - 2 * atrd, 2),
                'tp': round(entry + 3 * atrd, 2),
                'atr': atrd,
                'rsi': curr_rsi,
                'desc': 'RSI(2) extremely oversold < 10'
            })

        # SHORT: RSI(2) crosses above 90 (extremely overbought)
        elif prev_rsi <= 90 and curr_rsi > 90:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'short',
                'entry': entry,
                'sl': round(entry + 2 * atrd, 2),
                'tp': round(entry - 3 * atrd, 2),
                'atr': atrd,
                'rsi': curr_rsi,
                'desc': 'RSI(2) extremely overbought > 90'
            })

    return signals


def _rsi2(c):
    n = len(c)
    r = np.full(n, 50.0)
    for i in range(2, n):
        delta = c[i] - c[i-1]
        gain = delta if delta > 0 else 0
        loss = -delta if delta < 0 else 0
        avg_gain = np.mean([c[i-1] - c[i-2] if c[i-1] - c[i-2] > 0 else 0 for i in range(max(2, i-1), i+1)])
        avg_loss = np.mean([-(c[i-1] - c[i-2]) if c[i-1] - c[i-2] < 0 else 0 for i in range(max(2, i-1), i+1)])
        # Use simple 2-period RSI
        if i >= 2:
            gains = [c[j] - c[j-1] for j in range(i-1, i+1) if c[j] - c[j-1] > 0]
            losses = [-(c[j] - c[j-1]) for j in range(i-1, i+1) if c[j] - c[j-1] < 0]
            ag = np.mean(gains) if gains else 0
            al = np.mean(losses) if losses else 0
            rs = ag / (al + 1e-10)
            r[i] = 100 - (100 / (1 + rs))
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
    res = trs[0]
    for k in range(1, p):
        res = (res * (p - 1) + trs[k]) / p
    return res
