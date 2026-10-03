"""
Donchian Channel Breakout Strategy
Entry: Price breaks above 20-period high (long) or below 20-period low (short)
Exit: EOD close
Stop: Entry +/- 2*ATR
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
        prev_entry = closes[i-1]

        # Donchian channel highs/lows
        hi_20 = max(highs[max(0,i-period):i])
        lo_20 = min(lows[max(0,i-period):i])

        # LONG: break above 20-day high
        if prev_entry <= hi_20 and entry > hi_20:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'long',
                'entry': entry,
                'sl': round(entry - 2 * atrd, 2),
                'tp': round(entry + 3 * atrd, 2),
                'atr': atrd,
                'desc': f'Donchian breakout above {hi_20:.2f}'
            })

        # SHORT: break below 20-day low
        elif prev_entry >= lo_20 and entry < lo_20:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'short',
                'entry': entry,
                'sl': round(entry + 2 * atrd, 2),
                'tp': round(entry - 3 * atrd, 2),
                'atr': atrd,
                'desc': f'Donchian breakdown below {lo_20:.2f}'
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
