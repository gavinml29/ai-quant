"""
RTZigzag - 逐个拉取30分钟K线数据（规避1次/分钟限频）
每次拉一只，间隔65秒
"""
import tushare as ts
import json
import os
import time
from datetime import datetime, timedelta

PRO = ts.pro_api("7c6d5a4c6a3e3536a176807bde2386d9da6e180be8404386a995edac")

STOCKS = [
    {"key": "smic",       "code": "688981.SH", "name": "中芯国际"},
    {"key": "gigadevice", "code": "603986.SH", "name": "兆易创新"},
    {"key": "goldwind",   "code": "002202.SZ", "name": "金风科技"},
    {"key": "bright",     "code": "688333.SH", "name": "铂力特"},
    {"key": "leader",     "code": "688017.SH", "name": "绿的谐波"},
    {"key": "siruixin",   "code": "688102.SH", "name": "斯瑞新材"},
    {"key": "montage",    "code": "688008.SH", "name": "澜起科技"},
]

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

end_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")

print(f"数据区间: {start_date} ~ {end_date}")
print(f"将逐个拉取，每只间隔65秒\n")

for i, stock in enumerate(STOCKS):
    key = stock["key"]
    code = stock["code"]
    name = stock["name"]

    # 检查是否已有数据
    filepath = os.path.join(DATA_DIR, f"{key}_30min.json")
    if os.path.exists(filepath):
        with open(filepath) as f:
            existing = json.load(f)
        if len(existing) > 100:
            print(f"[{i+1}/{len(STOCKS)}] {name}: 已有 {len(existing)} 条，跳过")
            continue

    print(f"[{i+1}/{len(STOCKS)}] 拉取 {name} ({code})...", end=" ", flush=True)

    try:
        df = PRO.stk_mins(ts_code=code, freq="30min",
                          start_date=start_date, end_date=end_date)

        if df is None or len(df) == 0:
            print("❌ 无数据")
        else:
            records = df.to_dict("records")
            records.sort(key=lambda x: x["trade_time"])
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            print(f"✅ {len(records)} 条")

    except Exception as e:
        print(f"❌ {e}")

    # 如果不是最后一只，等待65秒
    if i < len(STOCKS) - 1:
        print(f"    等待65秒...", end=" ", flush=True)
        time.sleep(65)
        print("OK")

print("\n全部完成！")
