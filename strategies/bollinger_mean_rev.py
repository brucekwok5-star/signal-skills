"""
Bollinger Bands Mean-Reversion Strategy
Entry: Price crosses below lower Bollinger Band (oversold)
Exit: Price crosses back above middle band (EMA20) = EOD close
Stop: Middle band + 2*ATR (symmetric)
"""

import numpy as np

def detect(df):
    signals = []
    closes = df['Close'].values
    highs  = df['High'].values
    lows   = df['Low'].values
    n = len(closes)
    if n < 20:
        return signals

    # Bollinger Bands (20-period, 2 std)
    period = 20
    for i in range(period, n):
        band = closes[max(0, i-period):i]
        mid  = np.mean(band)
        std  = np.std(band)
        lower = mid - 2 * std
        upper = mid + 2 * std

        # ATR for stop
        atrd = _atr(highs, lows, closes, i, 14)
        if atrd is None:
            continue

        entry = closes[i]  # today's close price (entry at close of signal bar)

        # LONG: price crosses below lower band
        prev_close = closes[i-1] if i > 0 else None
        if prev_close is not None:
            was_above = prev_close >= lower
            is_below   = entry < lower
            if was_above and is_below:
                sl = mid + 2 * atrd
                tp = mid  # mean-revert to middle band
                signals.append({
                    'date': df.index[i] if hasattr(df, 'index') else i,
                    'direction': 'long',
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'atr': atrd,
                    'desc': 'BB oversold cross below lower band'
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
