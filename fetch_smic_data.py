#!/usr/bin/env python3
"""获取中芯国际 (688981.SH) 近一年日线数据"""

import os
import json
import sys
import tushare as ts

TOKEN = "7c6d5a4c6a3e3536a176807bde2386d9da6e180be8404386a995edac"
TS_CODE = "688981.SH"
OUTPUT_DIR = "/Users/gavin/WorkBuddy/AiQuant/data"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "smic_daily.json")

def main():
    ts.set_token(TOKEN)
    pro = ts.pro_api()

    # 近一年: 2025-06-29 ~ 2026-06-29
    start_date = "20250629"
    end_date = "20260629"

    print(f"获取 {TS_CODE} 日线数据: {start_date} ~ {end_date}")

    # 获取日线行情
    df = pro.daily(
        ts_code=TS_CODE,
        start_date=start_date,
        end_date=end_date,
    )

    if df is None or df.empty:
        print("错误: 未获取到数据")
        sys.exit(1)

    # 按日期升序排列
    df = df.sort_values("trade_date").reset_index(drop=True)

    print(f"获取到 {len(df)} 条记录")

    # 转为 JSON
    records = df.to_dict(orient="records")

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"数据已保存到: {OUTPUT_FILE}")

    # 打印摘要
    print(f"\n数据摘要:")
    print(f"  日期范围: {records[-1]['trade_date']} ~ {records[0]['trade_date']}")
    print(f"  开盘价范围: {df['open'].min():.2f} ~ {df['open'].max():.2f}")
    print(f"  收盘价范围: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
    print(f"  最高价: {df['high'].max():.2f}")
    print(f"  最低价: {df['low'].min():.2f}")
    print(f"  成交量范围: {df['vol'].min():,} ~ {df['vol'].max():,}")

    # 输出文件大小
    size = os.path.getsize(OUTPUT_FILE)
    print(f"  文件大小: {size:,} bytes")

if __name__ == "__main__":
    main()
