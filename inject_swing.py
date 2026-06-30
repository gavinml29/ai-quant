#!/usr/bin/env python3
import json

TPL = "/Users/gavin/WorkBuddy/AiQuant/outputs/swing_extrema_dashboard.html"

with open(TPL) as f:
    html = f.read()

with open("/Users/gavin/WorkBuddy/AiQuant/data/smic_daily.json") as f:
    smic = json.load(f)
with open("/Users/gavin/WorkBuddy/AiQuant/data/gigadevice_daily.json") as f:
    giga = json.load(f)
with open("/Users/gavin/WorkBuddy/AiQuant/data/swing_extrema.json") as f:
    extrema = json.load(f)

html = html.replace("__SMIC__", json.dumps(smic, ensure_ascii=False))
html = html.replace("__GIGA__", json.dumps(giga, ensure_ascii=False))
html = html.replace("__EXTREMA__", json.dumps(extrema, ensure_ascii=False))

with open(TPL, "w") as f:
    f.write(html)

print(f"波峰波谷看板已生成: {TPL}")
