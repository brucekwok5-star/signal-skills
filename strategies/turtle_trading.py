"""
Turtle Trading Strategy (Long Only)
Entry: Price breaks above 20-day high = long
Exit: EOD close
Stop: 2*ATR below entry
Rules: Enter on 20-day breakout, add 0.5ATR pyramid units, exit on 10-day low
Note: Simplified to single-unit entry with 20-day breakout rule
"""

import numpy as np

def detect(df):
    signals = []
    closes = df['close'].values
    highs  = df['high'].values
    lows   = df['low'].values
    n = len(closes)
    if n < 20:
        return signals

    period = 20

    for i in range(period, n):
        atrd = _atr(highs, lows, closes, i, 14)
        if atrd is None:
            continue

        entry = closes[i]
        prev_c = closes[i-1]

        # 20-day high breakout
        hi_20 = max(highs[max(0, i-period):i])
        lo_10 = min(lows[max(0, i-10):i]) if i >= 10 else lows[0]

        # LONG: break above 20-day high
        if prev_c <= hi_20 and entry > hi_20:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'long',
                'entry': entry,
                'sl': round(entry - 2 * atrd, 2),
                'tp': round(entry + 3 * atrd, 2),
                'atr': atrd,
                'desc': f'Turtle long on 20d high breakout {hi_20:.2f}'
            })

        # EXIT LONG: price falls below 10-day low
        if entry <= lo_10:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'exit_long',
                'entry': entry,
                'atr': atrd,
                'desc': f'Turtle exit on 10d low {lo_10:.2f}'
            })

    return signals


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
