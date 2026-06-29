#!/usr/bin/env python3
"""将数据注入量价分析仪表盘 HTML"""

import json

TPL = "/Users/gavin/WorkBuddy/AiQuant/outputs/volume_price_dashboard.html"
OUT = "/Users/gavin/WorkBuddy/AiQuant/outputs/volume_price_dashboard.html"

with open(TPL) as f:
    html = f.read()

with open("/Users/gavin/WorkBuddy/AiQuant/data/smic_daily.json") as f:
    smic_data = json.load(f)
with open("/Users/gavin/WorkBuddy/AiQuant/data/gigadevice_daily.json") as f:
    giga_data = json.load(f)
with open("/Users/gavin/WorkBuddy/AiQuant/data/volume_price_analysis.json") as f:
    sig_data = json.load(f)

html = html.replace("__SMIC_DATA__", json.dumps(smic_data, ensure_ascii=False))
html = html.replace("__GIGA_DATA__", json.dumps(giga_data, ensure_ascii=False))
html = html.replace("__SMIC_SIG__", json.dumps(sig_data["smic"], ensure_ascii=False))
html = html.replace("__GIGA_SIG__", json.dumps(sig_data["gigadevice"], ensure_ascii=False))

with open(OUT, "w") as f:
    f.write(html)

print(f"量价分析仪表盘已生成: {OUT}")
print(f"  中芯国际: {len(smic_data)}条数据, {len(sig_data['smic']['buy_signals'])}买/{len(sig_data['smic']['sell_signals'])}卖")
print(f"  兆易创新: {len(giga_data)}条数据, {len(sig_data['gigadevice']['buy_signals'])}买/{len(sig_data['gigadevice']['sell_signals'])}卖")
