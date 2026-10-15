"""
Short Squeeze Detection Strategy
Based on: gamma squeeze / short squeeze research 2024-2026
Logic: A short squeeze occurs when:
  1. Price jumps > 3% in a single day (showing urgency to cover shorts)
  2. Volume is significantly above the 20-day average (> 2x)
  3. Prior day had a large price decline (shorts added)
This combination forces short sellers to cover, pushing price further up.
Entry: Open price on signal day
Exit: EOD close
Stop: Entry - 2 * ATR (short squeeze is a reversal, so tight stop)
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

    # Volume SMA
    vol = df['Volume'].values.astype(float)
    vol_sma20 = np.full(n, np.nan)
    for i in range(20, n):
        vol_sma20[i] = np.mean(vol[i-20:i])

    # 14-period ATR
    at = np.full(n, np.nan)
    for i in range(14, n):
        tr = max(highs[i]-lows[i],
                 abs(highs[i]-closes[i-1]),
                 abs(lows[i]-closes[i-1]))
        at[i] = (at[i-1]*13 + tr)/14 if not np.isnan(at[i-1]) else tr

    for i in range(25, n):
        atrd = float(at[i])
        if atrd <= 0 or np.isnan(vol_sma20[i]) or vol_sma20[i] <= 0:
            continue

        entry = float(df['Open'].values[i])
        prev_close = float(closes[i-1])
        prev_open  = float(df['Open'].values[i-1])

        # Prior day: large decline (> 2% from open to close) → shorts built
        prev_oc_range = (prev_close - prev_open) / prev_open * 100

        # Today: big up day (> 3%) on above-average volume
        today_chg = (entry - prev_close) / prev_close * 100
        vol_ratio = vol[i] / vol_sma20[i]

        # Short squeeze long: prior drop + today's gap/rebound on high volume
        if prev_oc_range < -2.0 and today_chg > 3.0 and vol_ratio > 2.0:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'long',
                'entry': entry,
                'sl': round(entry - 2 * atrd, 4),
                'tp': 0,
                'atr': atrd,
                'desc': f'Short squeeze long: prev_drop={prev_oc_range:.1f}%, today={today_chg:.1f}%, vol_ratio={vol_ratio:.1f}x'
            })

    return signals