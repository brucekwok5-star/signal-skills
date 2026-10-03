"""
VWAP Reversal Strategy
Entry: Price crosses below VWAP (long) or above VWAP (short)
Exit: EOD close
Stop: Entry +/- 2*ATR
"""

import numpy as np

def detect(df):
    signals = []
    closes = df['Close'].values
    highs  = df['High'].values
    lows   = df['Low'].values
    volumes = df['Volume'].values if 'Volume' in df.columns else np.ones_like(closes)
    n = len(closes)
    if n < 20:
        return signals

    for i in range(20, n):
        atrd = _atr(highs, lows, closes, i, 14)
        if atrd is None:
            continue

        # VWAP = cumulative(price * volume) / cumulative(volume)
        typical = (highs[i] + lows[i] + closes[i]) / 3
        cum_pv = np.sum(typical * volumes[max(0,i-20):i+1])
        cum_v  = np.sum(volumes[max(0,i-20):i+1])
        vwap = cum_pv / (cum_v + 1e-10)

        prev_c = closes[i-1]
        curr_c = closes[i]

        # LONG: price crosses below VWAP
        if prev_c >= vwap and curr_c < vwap:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'long',
                'entry': curr_c,
                'sl': round(curr_c - 2 * atrd, 2),
                'tp': round(curr_c + 3 * atrd, 2),
                'atr': atrd,
                'desc': f'Price below VWAP {vwap:.2f}'
            })

        # SHORT: price crosses above VWAP
        elif prev_c <= vwap and curr_c > vwap:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'short',
                'entry': curr_c,
                'sl': round(curr_c + 2 * atrd, 2),
                'tp': round(curr_c - 3 * atrd, 2),
                'atr': atrd,
                'desc': f'Price above VWAP {vwap:.2f}'
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
