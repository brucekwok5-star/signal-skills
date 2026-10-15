"""
Percentile Mean-Reversion Strategy
Based on: volatility-scaled momentum/mean-reversion research (2024-2025)
Logic: When a stock's daily range (High-Low)/Close exceeds the 90th percentile
       of its own 20-day range distribution, the stock is in an "abnormally
       volatile" state. In such states, price tends to mean-revert — the 
       high-volatility bar represents an overextension that corrects by EOD.
       This is the "volatility compression" signal.
Entry: Open price on signal day
Exit: EOD close
Stop: Open +/- 0.5 * ATR (tight — mean reversion should happen quickly)
"""

import numpy as np

def detect(df):
    signals = []
    closes = df['Close'].values
    highs  = df['High'].values
    lows   = df['Low'].values
    n = len(closes)
    if n < 25:
        return signals

    # Compute daily range as % of close
    range_pct = np.full(n, np.nan)
    for i in range(1, n):
        range_pct[i] = (highs[i] - lows[i]) / closes[i] * 100

    # 20-day percentile rank of range %
    pct_rank = np.full(n, np.nan)
    for i in range(20, n):
        window = range_pct[i-20:i]
        valid = window[~np.isnan(window)]
        if len(valid) >= 15:
            count_below = np.sum(valid < range_pct[i])
            pct_rank[i] = count_below / len(valid) * 100

    # 14-period ATR
    at = np.full(n, np.nan)
    for i in range(14, n):
        tr = max(highs[i]-lows[i],
                 abs(highs[i]-closes[i-1]),
                 abs(lows[i]-closes[i-1]))
        at[i] = (at[i-1]*13 + tr)/14 if not np.isnan(at[i-1]) else tr

    for i in range(25, n):
        atrd = float(at[i])
        if atrd <= 0 or np.isnan(pct_rank[i]):
            continue

        entry = float(df['Open'].values[i])

        # 90th percentile → abnormally volatile → expect mean reversion
        if pct_rank[i] >= 90:
            prev_close = float(closes[i-1])
            # Mean-revert: if opened higher than previous close, short (overextended up)
            # if opened lower, long (overextended down)
            if entry > prev_close:
                signals.append({
                    'date': df.index[i] if hasattr(df, 'index') else i,
                    'direction': 'short',
                    'entry': entry,
                    'sl': round(entry + 0.5 * atrd, 4),
                    'tp': round(prev_close, 4),
                    'atr': atrd,
                    'desc': f'PctRank mean-rev short: 90th pctile range={range_pct[i]:.1f}%, opened above prev close'
                })
            elif entry < prev_close:
                signals.append({
                    'date': df.index[i] if hasattr(df, 'index') else i,
                    'direction': 'long',
                    'entry': entry,
                    'sl': round(entry - 0.5 * atrd, 4),
                    'tp': round(prev_close, 4),
                    'atr': atrd,
                    'desc': f'PctRank mean-rev long: 90th pctile range={range_pct[i]:.1f}%, opened below prev close'
                })

    return signals