#!/usr/bin/env python3
"""注入数据到主力分析仪表盘"""

import json

TPL = "/Users/gavin/WorkBuddy/AiQuant/outputs/main_force_dashboard.html"

with open(TPL) as f:
    html = f.read()

with open("/Users/gavin/WorkBuddy/AiQuant/data/smic_daily.json") as f:
    smic = json.load(f)
with open("/Users/gavin/WorkBuddy/AiQuant/data/gigadevice_daily.json") as f:
    giga = json.load(f)
with open("/Users/gavin/WorkBuddy/AiQuant/data/main_force_analysis.json") as f:
    force = json.load(f)

html = html.replace("__SMIC__", json.dumps(smic, ensure_ascii=False))
html = html.replace("__GIGA__", json.dumps(giga, ensure_ascii=False))
html = html.replace("__FORCE__", json.dumps(force, ensure_ascii=False))

with open(TPL, "w") as f:
    f.write(html)

print(f"主力分析仪表盘已生成: {TPL}")
