#!/usr/bin/env python3
"""
US Live Signal Scanner — signal-skills strategies
Strategies: %R Mean-Reversion, Gap Fill, Volatility Breakout
Data: qt.gtimg.cn (live quotes) + yfinance (90d history)
Usage: ~/.hermes/hermes-agent/venv/bin/python us_live_scan.py
"""
import urllib.request, time, numpy as np, yfinance as yf

US_UNIVERSE = ['AAPL','AMD','AMZN','ARM','AVGO','CRWD','CRWV','DELL','GDS','GOOG',
               'GOOGL','HOOD','INTC','LEGN','LITE','LLY','META','MRNA','MRVL','MSFT',
               'MSTR','MU','NBIS','NVDA','ORCL','PLTR','SMH','SNDK','SOXL','SOXX',
               'SPY','STX','TSLA','TSM','WDC','WMT','CRM','SMCI','QQQ']


def atr(h, l, c, p=14):
    n = len(c); tr = np.abs(h - l); r = np.full(n, np.nan)
    if n < p: return r
    r[p - 1] = np.mean(tr[:p])
    for i in range(p, n): r[i] = (r[i - 1] * (p - 1) + tr[i]) / p
    return r


def williams_r(h, l, c, p=14):
    n = len(c); r = np.full(n, np.nan)
    for i in range(p - 1, n):
        hp = np.max(h[i - p + 1:i + 1]); lp = np.min(l[i - p + 1:i + 1])
        if hp != lp: r[i] = -100 * (hp - c[i]) / (hp - lp)
    return r


def fetch_live(universe):
    live = {}
    for sym in universe:
        try:
            url = f'https://qt.gtimg.cn/q=us{sym}'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as r:
                raw = r.read().decode('gbk', errors='replace')
            parts = raw.strip().split('~')
            if len(parts) < 10: continue
            live[sym] = {'price': float(parts[3]), 'prev': float(parts[4]),
                         'chg': float(parts[32]) if parts[32] else 0.0,
                         'ts': parts[30] if len(parts) > 30 else '?'}
        except Exception:
            pass
        time.sleep(0.05)
    return live


def fetch_history(universe):
    hist = {}
    for sym in universe:
        try:
            df = yf.Ticker(sym).history(period='90d', auto_adjust=True)
            if len(df) >= 60:
                hist[sym] = {'closes': df['Close'].values.astype(float),
                             'highs': df['High'].values.astype(float),
                             'lows': df['Low'].values.astype(float)}
        except Exception:
            pass
        time.sleep(0.05)
    return hist


def build_rows(live, hist):
    rows = []
    for sym in US_UNIVERSE:
        if sym not in live or sym not in hist: continue
        price = live[sym]['price']; prev = live[sym]['prev']; chg = live[sym]['chg']
        if price <= 0: continue
        c = hist[sym]['closes']; h = hist[sym]['highs']; l = hist[sym]['lows']
        n = len(c)
        at = atr(h, l, c, 14); atrd = at[-1] if not np.isnan(at[-1]) else 0
        if atrd <= 0: continue
        gap = (price - prev) / prev * 100 if prev > 0 else 0
        wrv = williams_r(h, l, c, 14)
        wr = wrv[-1] if not np.isnan(wrv[-1]) else -50
        hp14 = np.max(h[-14:]); lp14 = np.min(l[-14:]); mid14 = (hp14 + lp14) / 2
        atr_pct = atrd / price * 100
        vb = None
        if n >= 20:
            high20 = np.max(h[-20:]); low20 = np.min(l[-20:])
            prev_c = c[-2] if n >= 2 else None
            if atr_pct > 3.0 and prev_c is not None and prev_c < high20 and price > high20: vb = 'up'
            elif atr_pct > 3.0 and prev_c is not None and prev_c > low20 and price < low20: vb = 'down'
        rows.append({'s': sym, 'p': price, 'c': chg, 'gap': gap, 'wr': wr, 'atr': atrd,
                     'mid': mid14, 'atr_pct': atr_pct, 'vb': vb})
    return rows


def tags(r, side):
    t = []
    if side == 'LONG':
        if r['wr'] < -80: t.append('%R Rev')
        if r['gap'] < -1.0: t.append('Gap Fill')
        if r['vb'] == 'up': t.append('Vol Break')
    else:
        if r['wr'] > -20: t.append('%R Rev')
        if r['gap'] > 1.0: t.append('Gap Fill')
        if r['vb'] == 'down': t.append('Vol Break')
    return t


def show(r, side):
    t = tags(r, side)
    if side == 'LONG':
        sl = r['p'] * 0.995; tp = r['mid']; rr = (tp - r['p']) / r['atr']
    else:
        sl = r['p'] * 1.005; tp = r['mid']; rr = (r['p'] - tp) / r['atr']
    return (f"  {r['s']:<8} {'+'.join(t):<22} ${r['p']:.2f}  {r['c']:+.2f}%  "
            f"gap={r['gap']:+.1f}%  %R={r['wr']:.1f}  SL=${sl:.2f}  TP=${tp:.2f}  "
            f"ATR={r['atr']:.2f}  R:R={rr:.1f}:1  agree={len(t)}")


def main():
    live = fetch_live(US_UNIVERSE)
    hist = fetch_history(US_UNIVERSE)
    rows = build_rows(live, hist)
    longs = [r for r in rows if tags(r, 'LONG')]
    shorts = [r for r in rows if tags(r, 'SHORT')]
    # Drop shorts with negative R:R (mechanical gap-flip collisions on oversold names)
    shorts = [r for r in shorts if (r['p'] - r['mid']) / r['atr'] > 0.5]
    L = sorted(longs, key=lambda r: (-len(tags(r, 'LONG')), -r['atr']))[:3]
    S = sorted(shorts, key=lambda r: (-len(tags(r, 'SHORT')), -r['atr']))[:3]
    ts = next(iter(live.values()))['ts'] if live else '?'
    print(f'Live: {len(live)} quotes @ {ts} | Long signals: {len(longs)} | Short signals: {len(shorts)}')
    print(f'\n{"=" * 82}\nTOP 3 LONG\n{"=" * 82}')
    for r in L: print(show(r, 'LONG'))
    print(f'\n{"=" * 82}\nTOP 3 SHORT\n{"=" * 82}')
    for r in S: print(show(r, 'SHORT'))


if __name__ == '__main__':
    main()
