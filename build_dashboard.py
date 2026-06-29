#!/usr/bin/env python3
"""将 Tushare 数据注入 HTML 模板，生成最终仪表盘"""

import json

TEMPLATE_PATH = "/Users/gavin/WorkBuddy/AiQuant/outputs/smic_dashboard.html"
DATA_PATH = "/Users/gavin/WorkBuddy/AiQuant/data/smic_daily.json"

with open(TEMPLATE_PATH, "r") as f:
    html = f.read()

with open(DATA_PATH, "r") as f:
    data = json.load(f)

# 注入数据
html = html.replace("{{DATA_PLACEHOLDER}}", json.dumps(data, ensure_ascii=False))

with open(TEMPLATE_PATH, "w") as f:
    f.write(html)

print(f"数据已注入，仪表盘已生成: {TEMPLATE_PATH}")
print(f"数据条目: {len(data)}")
