#!/usr/bin/env python3
"""对金风科技和铂力特做波段极值分析，追加到 swing_extrema.json"""

import json, os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from swing_extrema import load_sorted, zigzag, volume_confirm

DIR = "/Users/gavin/WorkBuddy/AiQuant/data"

NEW = [
    ("002202.SZ", "金风科技", "goldwind"),
    ("688333.SH", "铂力特", "bright"),
]

output = {}
for code, name, key in NEW:
    fpath = os.path.join(DIR, f"{key}_daily.json")
    data = load_sorted(fpath)
    # min_pct=3 配合 200块以下的用3%，高价股适当加大
    m_pct = 5 if key == "bright" else 4
    peaks, troughs = zigzag(data, min_pct=m_pct)
    c_peaks, c_troughs = volume_confirm(data, peaks, troughs)
    output[key] = {
        "name": name, "code": code, "min_pct": m_pct,
        "peaks": [{k: v for k, v in p.items() if k != "idx"} for p in c_peaks],
        "troughs": [{k: v for k, v in t.items() if k != "idx"} for t in c_troughs],
        "all_peaks_idx": [p["idx"] for p in c_peaks],
        "all_troughs_idx": [t["idx"] for t in c_troughs],
    }
    print(f"  {name}: {len(c_peaks)}波峰 + {len(c_troughs)}波谷 (min_pct={m_pct}%)")

# 合并到已有文件
exist_path = os.path.join(DIR, "swing_extrema.json")
with open(exist_path) as f:
    exist = json.load(f)
exist.update(output)
with open(exist_path, "w") as f:
    json.dump(exist, f, ensure_ascii=False, indent=2)
print(f"\n已合并到: {exist_path}")
print(f"现有: {list(exist.keys())}")
