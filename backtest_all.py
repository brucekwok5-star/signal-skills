#!/usr/bin/env python3
"""
New Strategy Backtester
Backtests all strategies in strategies/ against 39 US stocks, 90-day lookback.
Entry = day Open, Exit = EOD Close.
Saves results to backtest_results/.
"""
import json, time, importlib.util, numpy as np, yfinance as yf
from datetime import datetime, timezone, timedelta
from pathlib import Path

US_UNIVERSE = [
    'AAPL','AMD','AMZN','ARM','AVGO','CRWD','CRWV','DELL','GDS','GOOG',
    'GOOGL','HOOD','INTC','LEGN','LITE','LLY','META','MRNA','MRVL','MSFT',
    'MSTR','MU','NBIS','NVDA','ORCL','PLTR','SMH','SNDK','SOXL','SOXX',
    'SPY','STX','TSLA','TSM','WDC','WMT','CRM','SMCI','QQQ'
]
PERIOD = '90d'
MAX_BARS = 90          # bars kept per symbol (overridable for robustness tests)
OUT_DIR = Path(__file__).parent / 'backtest_results'
OUT_DIR.mkdir(exist_ok=True)
STRAT_DIR = Path(__file__).parent / 'strategies'

def _market_open_now():
    """True if US market has NOT closed yet (so today's bar is still partial)."""
    # US equities: 09:30-16:00 ET. ET is UTC-4 (EDT) or UTC-5 (EST).
    ny = timezone(timedelta(hours=-4))
    now_ny = datetime.now(timezone.utc).astimezone(ny)
    if now_ny.weekday() >= 5:          # weekend
        return False
    minutes = now_ny.hour * 60 + now_ny.minute
    return minutes < 16 * 60           # before 16:00 ET close

def get_bars(sym):
    df = yf.Ticker(sym).history(period=PERIOD, auto_adjust=True).tail(MAX_BARS).reset_index()
    # Drop the in-progress bar: yfinance returns today's partial bar while the
    # market is open. Backtesting on it would treat an unfinished session as a
    # completed day, contaminating the most recent trade's entry/exit.
    if len(df) >= 20 and _market_open_now():
        last_date = df['Date'].iloc[-1]
        last_date = last_date.date() if hasattr(last_date, 'date') else last_date
        if str(last_date) == str(datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-4))).date()):
            df = df.iloc[:-1].reset_index(drop=True)
    return df if len(df) >= 20 else None

def load_strategies():
    loaded = []
    for f in sorted(STRAT_DIR.glob('*.py')):
        if f.name == '__init__.py':
            continue
        spec = importlib.util.spec_from_file_location(f.stem, f)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            continue
        if hasattr(mod, 'detect'):
            loaded.append({'name': f.stem, 'detect': mod.detect})
    return loaded

def agg(rs):
    if not rs:
        return {'n': 0, 'wr': 0, 'avg_r': 0, 'total_r': 0, 'pf': 0}
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    pf = sum(wins)/abs(sum(losses)) if losses else 999
    return {
        'n': len(rs), 'wr': round(len(wins)/len(rs)*100, 1),
        'avg_r': round(sum(rs)/len(rs), 4), 'total_r': round(sum(rs), 2),
        'pf': round(pf, 3) if pf != 999 else 999
    }

def backtest(name, detect_fn):
    all_trades, ls, ss = [], [], []
    for sym in US_UNIVERSE:
        bars = get_bars(sym)
        if bars is None:
            continue
        n = len(bars)
        closes = bars['Close'].values.astype(float)
        highs  = bars['High'].values.astype(float)
        lows   = bars['Low'].values.astype(float)
        opens  = bars['Open'].values.astype(float)

        # 14-period ATR (Wilder smoothing)
        at = np.full(n, np.nan)
        if n < 14:
            continue
        tr_list = []
        for i in range(14):
            tr_list.append(max(highs[i]-lows[i], abs(highs[i]-closes[i-1]) if i > 0 else highs[i]-lows[i], abs(lows[i]-closes[i-1]) if i > 0 else highs[i]-lows[i]))
        at[13] = sum(tr_list) / 14
        for i in range(14, n):
            tr = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
            at[i] = (at[i-1] * 13 + tr) / 14

        try:
            raw_signals = detect_fn(bars)
        except Exception:
            continue

        for sig in raw_signals:
            direction = sig.get('direction', '')
            if direction not in ('long', 'short'):
                continue

            sig_date = sig.get('date')
            bar_idx = n - 1
            if sig_date is not None:
                for j in range(n):
                    if str(bars.index[j]) == str(sig_date) or j == sig_date:
                        bar_idx = j
                        break
                else:
                    try:
                        bar_idx = int(sig_date)
                    except (ValueError, TypeError):
                        bar_idx = n - 1

            # Need signal bar + next bar for entry/exit
            if bar_idx < 0 or bar_idx >= n - 2:
                continue

            # entry = next bar open, exit = next bar close
            entry = float(opens[bar_idx + 1])
            exit_p = float(closes[bar_idx + 1])
            atrd = float(at[bar_idx])  # ATR from signal day
            if np.isnan(atrd) or atrd <= 0:
                continue

            # The strategy anchors its SL/TP to the SIGNAL day's open, but we
            # enter at the NEXT bar's open. Re-anchor the stop to the actual
            # entry, preserving the strategy's intended stop distance. Without
            # this, a gap-down makes the stop land at/near entry -> degenerate
            # risk -> R explodes to hundreds and poisons the mean.
            sig_entry = float(sig.get('entry', entry))
            sig_sl = float(sig.get('sl', 0))
            if sig_sl:
                stop_dist = abs(sig_entry - sig_sl)
                sl = entry - stop_dist if direction == 'long' else entry + stop_dist
            else:
                sl = entry - 2*atrd if direction == 'long' else entry + 2*atrd
            tp_val = sig.get('tp')
            tp = float(tp_val) if tp_val else 0
            if tp:
                tp_dist = abs(sig_entry - float(tp_val))
                tp = entry + tp_dist if direction == 'long' else entry - tp_dist

            risk = abs(entry - sl)
            if risk <= 0:
                continue
            # Hard guard against degenerate risk: a stop placed essentially AT
            # the entry price makes R explode into the hundreds and poisons the
            # mean. Require the stop to be at least 0.1% of entry price away.
            # (ATR-scaled floors are too strict for fixed-percent-stop
            # strategies like gap_fill, whose 0.5% stop is legitimately tighter
            # than 0.25*ATR on high-volatility names.)
            if risk < 0.001 * entry:
                continue

            # Exit model: if the stop or target was actually touched during the
            # entry session, close AT that level. Only fall back to the EOD
            # close when neither was hit. Ignoring this lets a trade that
            # blew through its stop report the (much larger) EOD loss, or a
            # trade that hit its target report a far larger EOD gain -- both
            # distort the R distribution.
            hit_sl = (direction=='long' and lows[bar_idx+1]<=sl) or (direction=='short' and highs[bar_idx+1]>=sl)
            hit_tp = tp > 0 and ((direction=='long' and highs[bar_idx+1]>=tp) or (direction=='short' and lows[bar_idx+1]<=tp))

            if hit_sl:
                exit_price = sl
            elif hit_tp:
                exit_price = tp
            else:
                exit_price = exit_p

            r = (exit_price - entry)/risk if direction == 'long' else (entry - exit_price)/risk
            # Cap the extreme tail defensively (still lets genuine 3:1 targets
            # through, but no single trade can dominate the mean).
            r = max(-2.0, min(5.0, r))

            trade = {'sym':sym,'dir':direction,'entry':round(entry,4),'exit':round(exit_price,4),
                     'sl':round(sl,4),'tp':round(tp,4) if tp else 0,'atr':round(atrd,4),
                     'r':round(r,4),'hit_sl':bool(hit_sl),'hit_tp':bool(hit_tp)}
            all_trades.append(trade)
            (ls if direction == 'long' else ss).append(r)

    return {'strategy': name, 'long': agg(ls), 'short': agg(ss),
             'combined': agg(ls + ss), 'trades': all_trades}

def main():
    strategies = load_strategies()
    print(f'Strategies loaded: {[s["name"] for s in strategies]}')

    for s in strategies:
        name = s['name']
        detect_fn = s['detect']
        print(f'\nBacktesting: {name}')
        t0 = time.time()
        result = backtest(name, detect_fn)
        print(f'  Long:  N={result["long"]["n"]}, WR={result["long"]["wr"]:.0f}%, AvgR={result["long"]["avg_r"]:+.3f}R')
        print(f'  Short: N={result["short"]["n"]}, WR={result["short"]["wr"]:.0f}%, AvgR={result["short"]["avg_r"]:+.3f}R')
        print(f'  Combined: N={result["combined"]["n"]}, AvgR={result["combined"]["avg_r"]:+.3f}R, PF={result["combined"]["pf"]}')
        print(f'  Time: {time.time()-t0:.1f}s')
        out = OUT_DIR / f'{name}.json'
        with open(out, 'w') as f:
            json.dump(result, f, indent=2)
        print(f'  Saved: {out}')

if __name__ == '__main__':
    main()
