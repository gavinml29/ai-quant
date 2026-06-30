#!/usr/bin/env python3
"""获取斯瑞新材数据并追加分析"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from swing_extrema import load_sorted, zigzag, volume_confirm
import tushare as ts

TOKEN = "7c6d5a4c6a3e3536a176807bde2386d9da6e180be8404386a995edac"
DIR = "/Users/gavin/WorkBuddy/AiQuant/data"
KEY = "siruixin"

ts.set_token(TOKEN)
pro = ts.pro_api()
df = pro.daily(ts_code="688102.SH", start_date="20250630", end_date="20260630")
df = df.sort_values("trade_date").reset_index(drop=True)
records = df.to_dict(orient="records")
with open(f"{DIR}/{KEY}_daily.json", "w") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
print(f"✅ 斯瑞新材 (688102.SH): {len(records)} 条, ¥{df['close'].min():.2f} ~ ¥{df['close'].max():.2f}")

data = load_sorted(f"{DIR}/{KEY}_daily.json")
peaks, troughs = zigzag(data, min_pct=4)
c_peaks, c_troughs = volume_confirm(data, peaks, troughs)
print(f"   波峰: {len(c_peaks)}, 波谷: {len(c_troughs)}")

with open(f"{DIR}/swing_extrema.json") as f:
    extrema = json.load(f)
extrema[KEY] = {
    "name": "斯瑞新材", "code": "688102.SH", "min_pct": 4,
    "peaks": [{k: v for k, v in p.items() if k != "idx"} for p in c_peaks],
    "troughs": [{k: v for k, v in t.items() if k != "idx"} for t in c_troughs],
}
with open(f"{DIR}/swing_extrema.json", "w") as f:
    json.dump(extrema, f, ensure_ascii=False, indent=2)
print("   已合并到 swing_extrema.json")
