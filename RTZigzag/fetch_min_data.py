"""
RTZigzag - 批量拉取30分钟K线数据
通过 Tushare Python SDK 拉取七只股票近2个月30分钟K线
"""
import tushare as ts
import json
import os
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

# 拉取近2个月数据
end_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")

print(f"数据区间: {start_date} ~ {end_date}")
print(f"股票数量: {len(STOCKS)}")
print()

for stock in STOCKS:
    key = stock["key"]
    code = stock["code"]
    name = stock["name"]

    print(f"正在拉取 {name} ({code})...", end=" ")

    try:
        df = PRO.stk_mins(ts_code=code, freq="30min",
                          start_date=start_date, end_date=end_date)

        if df is None or len(df) == 0:
            print("❌ 无数据")
            continue

        # 转换为列表字典，排序（旧→新）
        records = df.to_dict("records")
        records.sort(key=lambda x: x["trade_time"])

        # 保存JSON
        filepath = os.path.join(DATA_DIR, f"{key}_30min.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        print(f"✅ {len(records)} 条，{records[0]['trade_time'][:10]} ~ {records[-1]['trade_time'][:10]}")

    except Exception as e:
        print(f"❌ 错误: {e}")

print("\n全部完成！")
