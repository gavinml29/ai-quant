#!/usr/bin/env python3
"""获取兆易创新数据并生成仪表盘"""

import json, os
import tushare as ts

TOKEN = "7c6d5a4c6a3e3536a176807bde2386d9da6e180be8404386a995edac"
TS_CODE = "603986.SH"

# 1. 获取数据
ts.set_token(TOKEN)
pro = ts.pro_api()
df = pro.daily(ts_code=TS_CODE, start_date="20250629", end_date="20260629")
df = df.sort_values("trade_date").reset_index(drop=True)
records = df.to_dict(orient="records")
print(f"获取到 {len(records)} 条记录")

# 2. 保存 JSON
os.makedirs("/Users/gavin/WorkBuddy/AiQuant/data", exist_ok=True)
json_path = "/Users/gavin/WorkBuddy/AiQuant/data/gigadevice_daily.json"
with open(json_path, "w") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
print(f"数据已保存: {json_path}")

# 3. 读取模板并注入数据
tpl_path = "/Users/gavin/WorkBuddy/AiQuant/outputs/smic_dashboard.html"
with open(tpl_path) as f:
    html = f.read()

html = html.replace("中芯国际 (688981)", "兆易创新 (603986)")
html = html.replace("<h1>中芯国际</h1>", "<h1>兆易创新</h1>")
html = html.replace("688981.SH · 科创板", "603986.SH · 沪市主板")
html = html.replace("中芯国际 (688981.SH)", "兆易创新 (603986.SH)")
html = html.replace("{{DATA_PLACEHOLDER}}", json.dumps(records, ensure_ascii=False))

out_path = "/Users/gavin/WorkBuddy/AiQuant/outputs/gigadevice_dashboard.html"
with open(out_path, "w") as f:
    f.write(html)
print(f"仪表盘已生成: {out_path}")

# 摘要
first = records[-1]; last = records[0]
print(f"\n价格范围: {df['close'].min():.2f} ~ {df['close'].max():.2f}")
print(f"日期: {first['trade_date']} ~ {last['trade_date']}")
