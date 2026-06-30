#!/usr/bin/env python3
"""澜起科技(688008) - 获取数据 + 波峰波谷分析"""

import json, os

DATA_DIR = "/Users/gavin/WorkBuddy/AiQuant/data"
EXTREMA_FILE = os.path.join(DATA_DIR, "swing_extrema.json")

# MCP 返回的数据已通过上下文传入，这里直接从 Tushare API 获取
import tushare as ts
pro = ts.pro_api("7c6d5a4c6a3e3536a176807bde2386d9da6e180be8404386a995edac")
df = pro.daily(ts_code="688008.SH", start_date="20250630", end_date="20260630")
records = df.to_dict("records")
for r in records:
    for k in ["open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]:
        if k in r:
            r[k] = float(r[k])

# 保存
with open(os.path.join(DATA_DIR, "montage_daily.json"), "w") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
print(f"Saved {len(records)} records to montage_daily.json")

# 按日期升序排序
records.sort(key=lambda x: x["trade_date"])

# ===== Zigzag 波峰波谷检测 =====
def zigzag(data, min_pct=3.0, lookback=8):
    n = len(data)
    all_peaks = []
    all_troughs = []

    for i in range(lookback, n - lookback):
        high = data[i]["high"]
        low = data[i]["low"]

        is_peak = all(data[i - j]["high"] <= high for j in range(1, lookback + 1)) and \
                  all(data[i + j]["high"] <= high for j in range(1, lookback + 1)) and \
                  any(data[i - j]["high"] < high for j in range(1, lookback + 1))

        is_trough = all(data[i - j]["low"] >= low for j in range(1, lookback + 1)) and \
                    all(data[i + j]["low"] >= low for j in range(1, lookback + 1)) and \
                    any(data[i - j]["low"] > low for j in range(1, lookback + 1))

        if is_peak:
            all_peaks.append({"idx": i, "price": high, "date": data[i]["trade_date"],
                              "close": data[i]["close"], "vol": data[i]["vol"],
                              "pct_chg": data[i]["pct_chg"]})
        if is_trough:
            all_troughs.append({"idx": i, "price": low, "date": data[i]["trade_date"],
                                "close": data[i]["close"], "vol": data[i]["vol"],
                                "pct_chg": data[i]["pct_chg"]})

    # 合并峰谷交替
    points = sorted(all_peaks + all_troughs, key=lambda x: x["idx"])
    merged = []
    last_type = None
    for p in points:
        t = "peak" if p in all_peaks else "trough"
        if t != last_type:
            merged.append((p["idx"], t, p))
            last_type = t
        elif t == "peak" and p["price"] > merged[-1][2]["price"]:
            merged[-1] = (p["idx"], t, p)
        elif t == "trough" and p["price"] < merged[-1][2]["price"]:
            merged[-1] = (p["idx"], t, p)

    # 幅度过滤
    peaks = []
    troughs = []
    last_extreme = None

    for idx, typ, p in merged:
        if last_extreme is None:
            if typ == "peak":
                peaks.append({**p, "from_trough_pct": 0.0})
                last_extreme = (idx, p["price"], "peak")
            else:
                troughs.append({**p, "from_peak_pct": 0.0})
                last_extreme = (idx, p["price"], "trough")
            continue

        change_pct = abs(p["price"] - last_extreme[1]) / last_extreme[1] * 100

        if change_pct < min_pct:
            if typ == "peak" and last_extreme[2] == "trough" and p["price"] > last_extreme[1]:
                last_extreme = (idx, p["price"], "peak")
            elif typ == "trough" and last_extreme[2] == "peak" and p["price"] < last_extreme[1]:
                last_extreme = (idx, p["price"], "trough")
            continue

        if typ == "peak" and last_extreme[2] == "trough":
            peaks.append({**p, "from_trough_pct": round(change_pct, 1)})
            last_extreme = (idx, p["price"], "peak")
        elif typ == "trough" and last_extreme[2] == "peak":
            troughs.append({**p, "from_peak_pct": round(change_pct, 1)})
            last_extreme = (idx, p["price"], "trough")

    return peaks, troughs


def volume_confirm(data, peaks, troughs):
    # 20日均量
    vols = [d["vol"] for d in data]
    ma20_vol = []
    for i in range(len(vols)):
        if i < 20:
            ma20_vol.append(sum(vols[:i + 1]) / (i + 1))
        else:
            ma20_vol.append(sum(vols[i - 19:i + 1]) / 20)

    for p in peaks:
        idx = p["idx"]
        vol_ratio = vols[idx] / ma20_vol[idx] if ma20_vol[idx] > 0 else 1
        p["vol_ratio"] = round(vol_ratio, 2)
        reasons = []
        if vol_ratio > 1.8:
            reasons.append("天量天价(放量见顶)")
        elif vol_ratio > 1.2:
            reasons.append("温和放量见顶")
        upper_shadow = (data[idx]["high"] - max(data[idx]["open"], data[idx]["close"])) / data[idx]["close"]
        if upper_shadow > 0.03:
            reasons.append("长上影线(抛压明显)")
        score = len(reasons) + (2 if vol_ratio > 1.8 else (1 if vol_ratio > 1.2 else 0))
        p["confidence"] = "强" if score >= 3 else ("中" if score >= 1 else "弱")
        p["reasons"] = reasons
        p["score"] = score

    for t in troughs:
        idx = t["idx"]
        vol_ratio = vols[idx] / ma20_vol[idx] if ma20_vol[idx] > 0 else 1
        t["vol_ratio"] = round(vol_ratio, 2)
        reasons = []
        if vol_ratio < 0.6:
            reasons.append("地量地价(缩量筑底)")
        lower_shadow = (min(data[idx]["open"], data[idx]["close"]) - data[idx]["low"]) / data[idx]["close"]
        if lower_shadow > 0.03:
            reasons.append("长下影线(支撑强劲)")
        if vol_ratio > 1.5 and data[idx]["pct_chg"] < -3:
            reasons.append("恐慌放量(资金接筹)")
        score = len(reasons) + (2 if vol_ratio < 0.6 else 0)
        t["confidence"] = "强" if score >= 3 else ("中" if score >= 1 else "弱")
        t["reasons"] = reasons
        t["score"] = score

    return peaks, troughs


peaks, troughs = zigzag(records, min_pct=3.0, lookback=8)
peaks, troughs = volume_confirm(records, peaks, troughs)

# 清理 idx（不需要序列化到 JSON）
for p in peaks:
    p.pop("idx", None)
for t in troughs:
    t.pop("idx", None)

result = {
    "name": "澜起科技",
    "code": "688008.SH",
    "peaks": peaks,
    "troughs": troughs,
}

print(f"\n澜起科技 (688008.SH)")
print(f"  波峰(卖出): {len(peaks)} 个")
for p in peaks:
    print(f"    {p['date']}  ¥{p['price']:.2f}  [{p['confidence']}] {', '.join(p['reasons'])}")
print(f"  波谷(买入): {len(troughs)} 个")
for t in troughs:
    print(f"    {t['date']}  ¥{t['price']:.2f}  [{t['confidence']}] {', '.join(t['reasons'])}")

# 合并到 swing_extrema.json
if os.path.exists(EXTREMA_FILE):
    with open(EXTREMA_FILE) as f:
        extrema = json.load(f)
else:
    extrema = {}

extrema["montage"] = result
with open(EXTREMA_FILE, "w") as f:
    json.dump(extrema, f, ensure_ascii=False, indent=2)
print(f"\nUpdated swing_extrema.json with 'montage' key")
