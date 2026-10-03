"""
Gap-Fill Mean-Reversion Strategy
Entry: Open gap > 1% from previous close -> fade the gap (short if gap up, long if gap down)
Exit: EOD close
Stop: Gap open price +/- 0.5% (very tight — mean-reversion should be quick)
"""

import numpy as np

def detect(df):
    signals = []
    closes = df['Close'].values
    highs  = df['High'].values
    lows   = df['Low'].values
    n = len(closes)
    if n < 2:
        return signals

    for i in range(1, n):
        atrd = _atr(highs, lows, closes, i, 14)
        if atrd is None:
            continue

        prev_close = closes[i-1]
        today_open = df['Open'].values[i] if 'Open' in df.columns else closes[i]
        entry = today_open

        gap_pct = (entry - prev_close) / prev_close * 100

        # LONG: gap down > 1%
        if gap_pct < -1.0:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'long',
                'entry': entry,
                'sl': round(entry * 0.995, 2),  # 0.5% stop
                'tp': round(prev_close, 2),      # target = prev close (fill the gap)
                'atr': atrd,
                'gap_pct': gap_pct,
                'desc': f'Gap-fill long: gap down {gap_pct:.1f}%'
            })

        # SHORT: gap up > 1%
        elif gap_pct > 1.0:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'short',
                'entry': entry,
                'sl': round(entry * 1.005, 2),  # 0.5% stop
                'tp': round(prev_close, 2),        # target = prev close (fill the gap)
                'atr': atrd,
                'gap_pct': gap_pct,
                'desc': f'Gap-fill short: gap up {gap_pct:.1f}%'
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
