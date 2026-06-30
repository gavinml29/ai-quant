"""
RTZigzag - 通过 WeStock Data 拉取分时数据并聚合为30分钟K线
WeStock minute 命令返回1分钟分时，最多5天
聚合为30分钟K线后约80根，足够做Zigzag分析
"""
import subprocess
import json
import os
import sys
from datetime import datetime
from collections import defaultdict

NODE = "/Users/gavin/.workbuddy/binaries/node/versions/22.22.2/bin/node"
WESTOCK = "/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/resources/builtin-skills/westock-data/scripts/index.js"

STOCKS = [
    {"key": "smic",       "westock_code": "sh688981", "name": "中芯国际"},
    {"key": "gigadevice", "westock_code": "sh603986", "name": "兆易创新"},
    {"key": "goldwind",   "westock_code": "sz002202", "name": "金风科技"},
    {"key": "bright",     "westock_code": "sh688333", "name": "铂力特"},
    {"key": "leader",     "westock_code": "sh688017", "name": "绿的谐波"},
    {"key": "siruixin",   "westock_code": "sh688102", "name": "斯瑞新材"},
    {"key": "montage",    "westock_code": "sh688008", "name": "澜起科技"},
]

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def fetch_minute_data(westock_code, days=5):
    """调用 WeStock 获取分时数据"""
    cmd = [NODE, WESTOCK, "minute", westock_code, "--days", str(days)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout


def parse_markdown_table(md_text):
    """解析 markdown 表格为字典列表"""
    lines = md_text.strip().split("\n")
    if len(lines) < 3:
        return []

    # 第一行是表头
    headers = [h.strip() for h in lines[0].split("|")[1:-1]]

    records = []
    for line in lines[2:]:  # 跳过表头和分割行
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) != len(headers):
            continue
        record = {}
        for h, c in zip(headers, cells):
            # 尝试数值转换
            try:
                val = float(c)
                if val == int(val):
                    val = int(val)
                record[h] = val
            except ValueError:
                record[h] = c
        records.append(record)

    return records


def aggregate_to_30min(minute_data):
    """将1分钟分时数据聚合为30分钟K线"""
    bars = defaultdict(list)

    for rec in minute_data:
        date = str(rec.get("date", ""))
        time_str = str(rec.get("time", "")).zfill(4)

        if len(time_str) < 4:
            continue

        hour = int(time_str[:2])
        minute = int(time_str[2:4])

        # 30分钟分桶
        bucket = "00" if minute < 30 else "30"
        bar_key = f"{date} {hour:02d}:{bucket}"

        bars[bar_key].append(rec)

    kline_30min = []
    for bar_key in sorted(bars.keys()):
        recs = bars[bar_key]
        if not recs:
            continue

        prices = [r["price"] for r in recs if "price" in r and isinstance(r["price"], (int, float))]
        vols = [r["volume"] for r in recs if "volume" in r and isinstance(r["volume"], (int, float))]
        amounts = [r["amount"] for r in recs if "amount" in r and isinstance(r["amount"], (int, float))]

        if not prices or not vols:
            continue

        # 解析日期时间
        date_str, time_part = bar_key.split(" ")
        hour = int(time_part[:2])
        minute_bucket = int(time_part[3:5])

        # 构造trade_time
        dt = datetime.strptime(date_str, "%Y%m%d")
        trade_time = dt.replace(hour=hour, minute=minute_bucket).strftime("%Y-%m-%d %H:%M:%S")

        kline_30min.append({
            "trade_time": trade_time,
            "open": prices[0],
            "close": prices[-1],
            "high": max(prices),
            "low": min(prices),
            "vol": sum(vols),
            "amount": sum(amounts),
        })

    return kline_30min


def main():
    print("=" * 60)
    print("RTZigzag 数据拉取 - WeStock Data 分时聚合")
    print("=" * 60)

    for stock in STOCKS:
        key = stock["key"]
        code = stock["westock_code"]
        name = stock["name"]

        print(f"\n[{name}] 拉取5日分时数据...", end=" ", flush=True)

        try:
            md_output = fetch_minute_data(code, days=5)
            records = parse_markdown_table(md_output)

            if not records:
                print("❌ 无数据")
                continue

            print(f"✅ {len(records)} 条1分钟数据")

            # 聚合为30分钟K线
            kline_30min = aggregate_to_30min(records)
            print(f"  → 聚合为 {len(kline_30min)} 根30分钟K线")

            if kline_30min:
                print(f"  时间范围: {kline_30min[0]['trade_time'][:16]} ~ {kline_30min[-1]['trade_time'][:16]}")

            # 保存
            filepath = os.path.join(DATA_DIR, f"{key}_30min.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(kline_30min, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"❌ 错误: {e}")

    print(f"\n{'='*60}")
    print("全部完成！")
    print(f"数据目录: {DATA_DIR}")


if __name__ == "__main__":
    main()
