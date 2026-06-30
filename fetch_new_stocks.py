#!/usr/bin/env python3
"""批量获取金风科技、铂力特近一年日线数据"""

import json, os
import tushare as ts

TOKEN = "7c6d5a4c6a3e3536a176807bde2386d9da6e180be8404386a995edac"
DIR = "/Users/gavin/WorkBuddy/AiQuant/data"

STOCKS = [
    ("002202.SZ", "金风科技", "goldwind"),
    ("688333.SH", "铂力特", "bright"),
]

ts.set_token(TOKEN)
pro = ts.pro_api()

for code, name, key in STOCKS:
    df = pro.daily(ts_code=code, start_date="20250630", end_date="20260630")
    df = df.sort_values("trade_date").reset_index(drop=True)
    records = df.to_dict(orient="records")
    fpath = os.path.join(DIR, f"{key}_daily.json")
    with open(fpath, "w") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"✅ {name} ({code}): {len(records)} 条 → {fpath}")
    print(f"   价格: ¥{df['close'].min():.2f} ~ ¥{df['close'].max():.2f}")
