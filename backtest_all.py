#!/usr/bin/env python3
"""
New Strategy Backtester
Backtests all strategies in strategies/ against 39 US stocks, 90-day lookback.
Entry = day Open, Exit = EOD Close.
Saves results to backtest_results/.
"""
import json, time, importlib.util, numpy as np, yfinance as yf
from pathlib import Path

US_UNIVERSE = [
    'AAPL','AMD','AMZN','ARM','AVGO','CRWD','CRWV','DELL','GDS','GOOG',
    'GOOGL','HOOD','INTC','LEGN','LITE','LLY','META','MRNA','MRVL','MSFT',
    'MSTR','MU','NBIS','NVDA','ORCL','PLTR','SMH','SNDK','SOXL','SOXX',
    'SPY','STX','TSLA','TSM','WDC','WMT','CRM','SMCI','QQQ'
]
PERIOD = '90d'
OUT_DIR = Path(__file__).parent / 'backtest_results'
OUT_DIR.mkdir(exist_ok=True)
STRAT_DIR = Path(__file__).parent / 'strategies'

def get_bars(sym):
    df = yf.Ticker(sym).history(period=PERIOD, auto_adjust=True).tail(90).reset_index()
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

        # 14-day ATR
        at = np.full(n, np.nan)
        for i in range(14, n):
            trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))]
            for j in range(i-13, i):
                trs.append(max(highs[j]-lows[j], abs(highs[j]-closes[j-1]), abs(lows[j]-closes[j-1])))
            at[i] = sum(trs[1:])/14 + (trs[0]-sum(trs[1:])/14)*(2/15) if len(trs) > 1 else trs[0]
            if i >= 15:
                at[i] = (at[i-1]*13 + trs[-1])/14

        try:
            raw_signals = detect_fn(bars)
        except Exception:
            continue

        for sig in raw_signals:
            direction = sig.get('direction', '')
            if direction not in ('long', 'short'):
                continue

            # Signal bar index
            sig_date = sig.get('date')
            bar_idx = n - 1  # default: last bar
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

            if bar_idx < 0 or bar_idx >= n - 1:
                continue

            entry = float(opens[bar_idx])
            exit_p = float(closes[bar_idx])
            atrd = float(at[bar_idx])
            if np.isnan(atrd) or atrd <= 0:
                continue

            sl = float(sig.get('sl', entry - 2*atrd) if direction == 'long' else entry + 2*atrd)
            tp_val = sig.get('tp')
            tp = float(tp_val) if tp_val else 0

            risk = abs(entry - sl)
            if risk <= 0:
                continue
            r = (exit_p - entry)/risk if direction == 'long' else (entry - exit_p)/risk

            hit_sl = (direction=='long' and lows[bar_idx]<=sl) or (direction=='short' and highs[bar_idx]>=sl)
            hit_tp = tp > 0 and ((direction=='long' and highs[bar_idx]>=tp) or (direction=='short' and lows[bar_idx]<=tp))

            trade = {'sym':sym,'dir':direction,'entry':round(entry,4),'exit':round(exit_p,4),
                     'sl':round(sl,4),'tp':round(tp,4) if tp else 0,'atr':round(atrd,4),
                     'r':round(r,4),'hit_sl':hit_sl,'hit_tp':hit_tp}
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
