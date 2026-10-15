"""
RSI Momentum Strategy (Shortened for 90-day backtest)
Logic: RSI(14) crossing above 50 with price above 20 EMA = bullish.
       RSI(14) crossing below 50 with price below 20 EMA = bearish.
       Uses 20-period EMA instead of 200-day for 90-day compatibility.
Entry: Open price on signal day
Exit: EOD close
Stop: Entry +/- 2 * ATR
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

    # RSI(14)
    period = 14
    rsi = np.full(n, np.nan)
    for i in range(period, n):
        deltas = np.diff(closes[i-period+1:i+1], prepend=closes[i-period])
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            rsi[i] = 100
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100 - (100 / (1 + rs))

    # 20-period EMA (instead of 200-day SMA for 90-day compatibility)
    ema20 = np.full(n, np.nan)
    for i in range(20, n):
        if i == 20:
            ema20[i] = np.mean(closes[i-20:i+1])
        else:
            ema20[i] = ema20[i-1] * 0.9 + closes[i] * 0.1

    # 14-period ATR
    at = np.full(n, np.nan)
    for i in range(14, n):
        tr = max(highs[i]-lows[i],
                 abs(highs[i]-closes[i-1]),
                 abs(lows[i]-closes[i-1]))
        at[i] = (at[i-1]*13 + tr)/14 if not np.isnan(at[i-1]) else tr

    for i in range(25, n):
        atrd = float(at[i])
        if atrd <= 0 or np.isnan(rsi[i]) or np.isnan(rsi[i-1]) or np.isnan(ema20[i]):
            continue

        entry = float(df['Open'].values[i])
        curr_price = float(closes[i])

        prev_rsi = float(rsi[i-1])
        curr_rsi = float(rsi[i])

        # Trend filter: price above 20 EMA = long bias, below = short bias
        above_trend = curr_price > ema20[i]
        below_trend = curr_price < ema20[i]

        # Long: RSI crosses above 50 AND price above 20 EMA
        if prev_rsi < 50 and curr_rsi >= 50 and above_trend:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'long',
                'entry': entry,
                'sl': round(entry - 2 * atrd, 4),
                'tp': 0,
                'atr': atrd,
                'desc': f'RSI momentum long: RSI={curr_rsi:.1f}, above 20 EMA'
            })

        # Short: RSI crosses below 50 AND price below 20 EMA
        elif prev_rsi > 50 and curr_rsi <= 50 and below_trend:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'short',
                'entry': entry,
                'sl': round(entry + 2 * atrd, 4),
                'tp': 0,
                'atr': atrd,
                'desc': f'RSI momentum short: RSI={curr_rsi:.1f}, below 20 EMA'
            })

    return signals