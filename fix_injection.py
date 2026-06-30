#!/usr/bin/env python3
"""快速修复：注入五只股票数据到看板"""
import json, re

DIR = "/Users/gavin/WorkBuddy/AiQuant"
HTML = f"{DIR}/outputs/swing_extrema_dashboard.html"

with open(HTML) as f:
    html = f.read()

RAW = {}
for key in ["smic", "gigadevice", "goldwind", "bright", "leader", "siruixin", "montage"]:
    with open(f"{DIR}/data/{key}_daily.json") as f:
        RAW[key] = json.load(f)

with open(f"{DIR}/data/swing_extrema.json") as f:
    extrema = json.load(f)

# 替换 const RAW = {...}; 块
raw_str = json.dumps(RAW, ensure_ascii=False)
html = re.sub(r'const RAW = \{.*?\};', f'const RAW = {raw_str};', html, count=1, flags=re.DOTALL)

# 替换 const EXTREMA = {...}; 块
ext_str = json.dumps(extrema, ensure_ascii=False)
html = re.sub(r'const EXTREMA = \{.*?\};', f'const EXTREMA = {ext_str};', html, count=1, flags=re.DOTALL)

with open(HTML, "w") as f:
    f.write(html)

# Verify
with open(HTML) as f:
    h = f.read()
idx = h.find('const RAW = ')
end = h.find('const EXTREMA', idx)
raw_test = h[idx+12:end].strip().rstrip(';')
r = json.loads(raw_test)
print(f"✅ RAW keys: {list(r.keys())}")
print(f"   sizes: {', '.join(f'{k}:{len(v)}' for k, v in r.items())}")
