import requests, os, time, threading, pandas as pd, numpy as np
from flask import Flask
from datetime import datetime

app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
BINANCE = "https://api.binance.com"

VOL_MIN, VOL_MAX = 2.0, 5.0
TIMEFRAMES = ["1h","4h","1d"]
MFI_THRESH = 20
sent_cache = {}

@app.route('/')
def home():
    return f"MFI Whale Bot ONLINE - {datetime.now()}"

def send(msg):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id":CHAT_ID,"text":msg,"parse_mode":"Markdown","disable_web_page_preview":True}, timeout=15)
    except: pass

def get_coins():
    try:
        url="https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1&sparkline=false"
        data=requests.get(url,timeout=20).json()
        symbols=[c['symbol'].upper()+"USDT" for c in data if (c.get('market_cap',0) or 0)>=100_000_000]
        ex=requests.get(f"{BINANCE}/api/v3/exchangeInfo",timeout=10).json()
        bset=set([s['symbol'] for s in ex['symbols'] if s['status']=='TRADING'])
        final=[s for s in symbols if s in bset and s not in ['USDCUSDT','FDUSDUSDT','TUSDUSDT']]
        return final[:150]
    except:
        return ["ASTERUSDT","BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","OPUSDT","ARBUSDT","AVAXUSDT","LINKUSDT","DOGEUSDT"]

def get_klines(sym, interval):
    url=f"{BINANCE}/api/v3/klines?symbol={sym}&interval={interval}&limit=100"
    try:
        r=requests.get(url,timeout=10)
        if r.status_code!=200: return None
        d=r.json()
        if len(d)<35: return None
        df=pd.DataFrame(d, columns=['t','o','h','l','c','v','a','b','c1','c2','c3','c4'])
        for col in ['o','h','l','c','v']: df[col]=df[col].astype(float)
        return df
    except: return None

def calc_mfi(df, period=14):
    tp = (df['h'] + df['l'] + df['c']) / 3
    mf = tp * df['v']
    pos_mf, neg_mf = 0, 0
    mfi_list = []
    # tính MFI chuẩn
    for i in range(1, len(tp)):
        if tp.iloc[i] > tp.iloc[i-1]:
            pos_mf = mf.iloc[i]
            neg_mf = 0
        else:
            pos_mf = 0
            neg_mf = mf.iloc[i]
        # rolling
        if i >= period:
            pos_sum = 0; neg_sum = 0
            for j in range(i-period+1, i+1):
                if tp.iloc[j] > tp.iloc[j-1]: pos_sum += mf.iloc[j]
                else: neg_sum += mf.iloc[j]
            if neg_sum==0: mfi=100
            else:
                mr=pos_sum/neg_sum
                mfi=100 - (100/(1+mr))
            mfi_list.append(mfi)
    return mfi_list[-1] if mfi_list else 50

def do_scan():
    global sent_cache
    coins=get_coins()
    print(f"Quét MFI {len(coins)} coin...")
    signals=[]
    now=datetime.now()
    for coin in coins:
        for tf in TIMEFRAMES:
            key=f"{coin}_{tf}"
            if key in sent_cache and (now-sent_cache[key]).total_seconds()<21600: continue
            df=get_klines(coin, tf)
            if df is None: continue
            try:
                mfi=calc_mfi(df)
                vol_x=df['v'].iloc[-1]/df['v'].iloc[-21:-1].mean()
                if mfi < MFI_THRESH and VOL_MIN <= vol_x <= VOL_MAX:
                    whale = "🐋 WHALE GOM" if vol_x >= 3.5 else "🐟 Gom nhẹ"
                    signals.append({"sym":coin,"tf":tf,"mfi":mfi,"vol":vol_x,"price":df['c'].iloc[-1],"whale":whale})
                    sent_cache[key]=now
            except: pass
            time.sleep(0.15)

    if signals:
        msg=f"💎 *MFI BẮT ĐÁY {now.strftime('%H:%M')}* 💎\n"
        msg+=f"ĐK: MFI < {MFI_THRESH} + Vol {VOL_MIN}x-{VOL_MAX}x\nTF: {','.join(TIMEFRAMES)}\n\n"
        for s in signals[:20]:
            icon = "🐋" if "WHALE" in s['whale'] else "💧"
            msg+=f"{icon} *{s['sym']}* [{s['tf'].upper()}] ${s['price']:.5f}\n"
            msg+=f" {s['whale']} | MFI:`{s['mfi']:.1f}` | Vol:x{s['vol']:.1f}\n"
            msg+=f" [📈 Trade](https://www.binance.com/en/trade/{s['sym']})\n\n"
        send(msg)
    return len(signals)

def scan_loop():
    send(f"✅ *MFI Whale Bot ONLINE* 🐋\n💧 MFI < {MFI_THRESH}\n📊 Vol {VOL_MIN}x-{VOL_MAX}x\n⏰ TF: {','.join(TIMEFRAMES)}\nLệnh: /scan /check /status")
    while True:
        try: do_scan()
        except Exception as e: print(e)
        time.sleep(1800)

threading.Thread(target=scan_loop, daemon=True).start()

if __name__=="__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT",10000)))
