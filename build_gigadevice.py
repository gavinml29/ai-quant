#!/usr/bin/env python3
"""生成兆易创新 HTML K线仪表盘"""

import json, os

DATA_FILE = "/Users/gavin/WorkBuddy/AiQuant/data/gigadevice_daily.json"
HTML_OUT = "/Users/gavin/WorkBuddy/AiQuant/outputs/gigadevice_dashboard.html"
TEMPLATE_FILE = "/Users/gavin/WorkBuddy/AiQuant/outputs/smic_dashboard.html"

with open(DATA_FILE) as f:
    raw_data = json.load(f)

# 读取模板,替换 title/header
with open(TEMPLATE_FILE) as f:
    tpl = f.read()

tpl = tpl.replace("中芯国际 (688981)", "兆易创新 (603986)")
tpl = tpl.replace("<h1>中芯国际</h1>", "<h1>兆易创新</h1>")
tpl = tpl.replace("688981.SH · 科创板", "603986.SH · 沪市主板")
tpl = tpl.replace("中芯国际 (688981.SH)", "兆易创新 (603986.SH)")

# 注入数据
tpl = tpl.replace("{{DATA_PLACEHOLDER}}", json.dumps(raw_data, ensure_ascii=False))

with open(HTML_OUT, "w") as f:
    f.write(tpl)

print(f"生成完成: {HTML_OUT} ({len(raw_data)} 条)")
