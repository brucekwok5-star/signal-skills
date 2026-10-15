"""
ADX Trend Following Strategy (Shortened for 90-day backtest)
Logic: ADX > 20 confirms a trending market. When +DI crosses above -DI,
       enter long. When -DI crosses above +DI, enter short.
       Uses 20-period EMA instead of 200-day SMA for compatibility.
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
    if n < 28:
        return signals

    period = 14
    at = np.full(n, np.nan)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        tr = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        if i >= period:
            at[i] = (at[i-1]*13 + tr)/14 if not np.isnan(at[i-1]) else tr

        up_move = highs[i] - highs[i-1]
        down_move = lows[i-1] - lows[i]
        if up_move > down_move:
            plus_dm[i] = up_move
        if down_move > up_move:
            minus_dm[i] = down_move

    # Wilder smooth DM
    s_plus = np.zeros(n)
    s_minus = np.zeros(n)
    for i in range(period, n):
        if i == period:
            s_plus[i] = np.sum(plus_dm[i-period+1:i+1])
            s_minus[i] = np.sum(minus_dm[i-period+1:i+1])
        else:
            s_plus[i] = s_plus[i-1] - s_plus[i-1]/period + plus_dm[i]
            s_minus[i] = s_minus[i-1] - s_minus[i-1]/period + minus_dm[i]

    di_plus = np.full(n, 0.0)
    di_minus = np.full(n, 0.0)
    dx = np.full(n, 0.0)

    for i in range(period, n):
        if at[i] > 0:
            di_plus[i] = 100 * s_plus[i] / at[i]
            di_minus[i] = 100 * s_minus[i] / at[i]
            did = di_plus[i] + di_minus[i]
            dx[i] = 100 * abs(di_plus[i] - di_minus[i]) / did if did > 0 else 0

    # ADX: 14-period Wilder smoothing of DX
    adx = np.full(n, 0.0)
    adx_vals = []
    for i in range(period, n):
        adx_vals.append(dx[i])
        if len(adx_vals) == period:
            adx[i] = np.mean(adx_vals)
        elif len(adx_vals) > period:
            adx[i] = (adx[i-1] * (period-1) + dx[i]) / period

    for i in range(period+1, n):
        if adx[i] < 20:
            continue
        entry = float(df['Open'].values[i])
        atrd = float(at[i])
        if atrd <= 0:
            continue

        curr_plus = di_plus[i]
        curr_minus = di_minus[i]
        prev_plus = di_plus[i-1]
        prev_minus = di_minus[i-1]

        if curr_plus == 0 or curr_minus == 0 or prev_plus == 0 or prev_minus == 0:
            continue

        # +DI crosses above -DI → long
        if prev_minus >= prev_plus and curr_plus > curr_minus:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'long',
                'entry': entry,
                'sl': round(entry - 2 * atrd, 4),
                'tp': 0,
                'atr': atrd,
                'desc': f'ADX trend long: ADX={adx[i]:.1f}, +DI>{curr_plus:.1f} over -DI={curr_minus:.1f}'
            })

        # -DI crosses above +DI → short
        elif prev_plus >= prev_minus and curr_minus > curr_plus:
            signals.append({
                'date': df.index[i] if hasattr(df, 'index') else i,
                'direction': 'short',
                'entry': entry,
                'sl': round(entry + 2 * atrd, 4),
                'tp': 0,
                'atr': atrd,
                'desc': f'ADX trend short: ADX={adx[i]:.1f}, -DI>{curr_minus:.1f} over +DI={curr_plus:.1f}'
            })

    return signals