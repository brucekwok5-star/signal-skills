"""
Volatility Breakout Strategy
Based on: volatility-scaled momentum research (2024-2025)
Logic: When ATR expands beyond 1.5x the 20-day ATR average, price tends to
       continue in the direction of the expansion. This captures momentum 
       eruptions that follow calm periods.
Entry: Open price on signal day
Exit: EOD close
Stop: Entry +/- 1.5 * current ATR
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

    # Compute 14-period ATR
    at = np.full(n, np.nan)
    for i in range(14, n):
        tr = max(highs[i]-lows[i],
                 abs(highs[i]-closes[i-1]),
                 abs(lows[i]-closes[i-1]))
        at[i] = (at[i-1]*13 + tr)/14 if not np.isnan(at[i-1]) else tr

    # 20-day moving average of ATR
    atr_sma = np.full(n, np.nan)
    for i in range(24, n):
        atr_sma[i] = np.mean(at[i-19:i+1])

    for i in range(25, n):
        if np.isnan(at[i]) or np.isnan(atr_sma[i]) or atr_sma[i] <= 0:
            continue

        entry = float(df['Open'].values[i])
        atrd  = float(at[i])

        # Volatility expansion: ATR > 1.5x 20-day ATR SMA
        if atrd < 1.5 * atr_sma[i]:
            continue

        # Look at prior bar direction to determine breakout direction
        if i < 1:
            continue

        prior_close = float(closes[i-1])
        prior_open  = float(df['Open'].values[i-1])
        prev_atr    = float(at[i-1])

        # Strong prior bar: close > open and range > prior ATR
        prior_range = highs[i-1] - lows[i-1]
        prior_was_strong = (prior_close > prior_open) and (prior_range > prev_atr)

        if prior_was_strong:
            # Upside breakout continuation
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'long',
                'entry': entry,
                'sl': round(entry - 1.5 * atrd, 4),
                'tp': 0,
                'atr': atrd,
                'desc': f'Volatility breakout long: ATR expanded {atrd/atr_sma[i]:.2f}x'
            })
        else:
            prior_was_weak = (prior_close < prior_open) and (prior_range > prev_atr)
            if prior_was_weak:
                signals.append({
                    'date': df.index[i] if hasattr(df, 'index') else i,
                    'direction': 'short',
                    'entry': entry,
                    'sl': round(entry + 1.5 * atrd, 4),
                    'tp': 0,
                    'atr': atrd,
                    'desc': f'Volatility breakout short: ATR expanded {atrd/atr_sma[i]:.2f}x'
                })

    return signals