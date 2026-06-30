#!/usr/bin/env python3
import json

TPL = "/Users/gavin/WorkBuddy/AiQuant/outputs/swing_extrema_dashboard.html"

with open(TPL) as f:
    html = f.read()

RAW = {}
DIR = "/Users/gavin/WorkBuddy/AiQuant/data"
for key in ["smic", "gigadevice", "goldwind", "bright"]:
    with open(f"{DIR}/{key}_daily.json") as f:
        RAW[key] = json.load(f)

with open(f"{DIR}/swing_extrema.json") as f:
    extrema = json.load(f)

html = html.replace("__RAW__", json.dumps(RAW, ensure_ascii=False))
html = html.replace("__EXTREMA__", json.dumps(extrema, ensure_ascii=False))

with open(TPL, "w") as f:
    f.write(html)

print(f"四股票波峰波谷看板已生成: {TPL}")
