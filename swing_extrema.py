#!/usr/bin/env python3
"""
波谷买入 / 波峰卖出 —— 基于量价关系的波段极值点检测

算法：
1. Zigzag 摆动点检测（最小幅度过滤噪点）
2. 量价确认：波谷缩量→筹码沉淀，波峰放量→主力出货
3. 生成买卖信号
"""

import json, os

DATA_DIR = "/Users/gavin/WorkBuddy/AiQuant/data"
OUT_DIR = "/Users/gavin/WorkBuddy/AiQuant/outputs"

SYMBOLS = {
    "smic": {"name": "中芯国际", "code": "688981.SH", "file": "smic_daily.json"},
    "gigadevice": {"name": "兆易创新", "code": "603986.SH", "file": "gigadevice_daily.json"},
}


def load_sorted(filepath):
    with open(filepath) as f:
        raw = json.load(f)
    data = []
    for d in sorted(raw, key=lambda x: x["trade_date"]):
        data.append({
            "date": d["trade_date"],
            "open": float(d["open"]),
            "close": float(d["close"]),
            "high": float(d["high"]),
            "low": float(d["low"]),
            "vol": float(d["vol"]),
            "amount": float(d["amount"]),
            "pct_chg": float(d["pct_chg"]),
        })
    return data


def zigzag(data, min_pct=5.0, lookback=8):
    """简化版波峰波谷检测"""
    n = len(data)

    # 第一步：找所有局部极值（关注收盘价）
    raw_extrema = []  # (idx, type, price, data)
    closes = [d["close"] for d in data]
    highs = [d["high"] for d in data]
    lows = [d["low"] for d in data]

    for i in range(lookback, n - lookback):
        is_peak = True
        is_trough = True
        for j in range(1, lookback + 1):
            if highs[i - j] >= highs[i] or highs[i + j] >= highs[i]:
                is_peak = False
            if lows[i - j] <= lows[i] or lows[i + j] <= lows[i]:
                is_trough = False
        if is_peak:
            raw_extrema.append(("peak", i, highs[i], data[i]))
        if is_trough:
            raw_extrema.append(("trough", i, lows[i], data[i]))

    if not raw_extrema:
        return [], []

    raw_extrema.sort(key=lambda x: x[1])  # 按时间排序

    # 第二步：合并连续同向极值（保留更极端的）
    merged = []
    current = raw_extrema[0]
    for i in range(1, len(raw_extrema)):
        nxt = raw_extrema[i]
        if nxt[0] == current[0]:  # 同类型
            if (current[0] == "peak" and nxt[2] > current[2]) or (current[0] == "trough" and nxt[2] < current[2]):
                current = nxt
        else:
            merged.append(current)
            current = nxt
    merged.append(current)

    # 第三步：幅度过滤（相邻极值至少 min_pct% 变化）
    peaks, troughs = [], []
    for i in range(1, len(merged)):
        prev_type, prev_idx, prev_price, prev_data = merged[i - 1]
        cur_type, cur_idx, cur_price, cur_data = merged[i]
        change_pct = abs(cur_price - prev_price) / prev_price * 100

        if change_pct >= min_pct:
            info = {"idx": cur_idx, "date": cur_data["date"],
                    "price": cur_price, "close": cur_data["close"],
                    "vol": cur_data["vol"], "pct_chg": cur_data["pct_chg"]}
            if cur_type == "peak":
                info["from_trough_pct"] = round(change_pct, 1) if prev_type == "trough" else 0
                peaks.append(info)
            else:
                info["from_peak_pct"] = round(change_pct, 1) if prev_type == "peak" else 0
                troughs.append(info)

    return peaks, troughs


def volume_confirm(data, peaks, troughs):
    """用成交量验证波峰波谷信号质量"""
    closes = [d["close"] for d in data]
    vols = [d["vol"] for d in data]

    # 计算成交量均线
    def ma(arr, n):
        r = [None] * len(arr)
        for i in range(n - 1, len(arr)):
            r[i] = sum(arr[i - n + 1 : i + 1]) / n
        return r

    vol20 = ma(vols, 20)
    vol60 = ma(vols, 60)

    confirmed_peaks = []
    confirmed_troughs = []

    for p in peaks:
        idx = p["idx"]
        v20 = vol20[idx] or 1
        v60 = vol60[idx] or 1
        vol_ratio = p["vol"] / v20

        # 波峰确认指标
        score = 0
        reasons = []

        # 1. 放量见顶（天量天价）
        if vol_ratio > 1.8:
            score += 3
            reasons.append("天量天价(放量见顶)")
        elif vol_ratio > 1.2:
            score += 1
            reasons.append("温和放量见顶")

        # 2. 滞涨信号（涨幅收窄但量不缩）
        if abs(p["pct_chg"]) < 1.5 and vol_ratio > 1.5:
            score += 2
            reasons.append("高位滞涨(量价背离)")

        # 3. 长上影线
        if data[idx]["high"] - max(data[idx]["open"], data[idx]["close"]) > data[idx]["close"] * 0.03:
            score += 2
            reasons.append("长上影线(抛压明显)")

        confidence = "强" if score >= 3 else "中" if score >= 1 else "弱"
        p["confidence"] = confidence
        p["vol_ratio"] = round(vol_ratio, 2)
        p["reasons"] = reasons
        p["score"] = score
        confirmed_peaks.append(p)

    for t in troughs:
        idx = t["idx"]
        v20 = vol20[idx] or 1
        vol_ratio = t["vol"] / v20

        score = 0
        reasons = []

        # 1. 缩量见底（地量地价）
        if vol_ratio < 0.6:
            score += 3
            reasons.append("地量地价(缩量筑底)")
        elif vol_ratio < 0.8:
            score += 1
            reasons.append("缩量接近底部")

        # 2. 放量反转（恐慌抛售后资金接盘）
        if vol_ratio > 1.5 and t["pct_chg"] < -3:
            score += 2
            reasons.append("恐慌放量(资金接筹)")

        # 3. 长下影线（探底回升）
        if min(data[idx]["open"], data[idx]["close"]) - data[idx]["low"] > data[idx]["close"] * 0.03:
            score += 2
            reasons.append("长下影线(支撑强劲)")

        confidence = "强" if score >= 3 else "中" if score >= 1 else "弱"
        t["confidence"] = confidence
        t["vol_ratio"] = round(vol_ratio, 2)
        t["reasons"] = reasons
        t["score"] = score
        confirmed_troughs.append(t)

    return confirmed_peaks, confirmed_troughs


def fmt(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def main():
    best_min_pct = 5
    for min_pct in [3, 5, 7, 10]:
        results = {}
        for key, info in SYMBOLS.items():
            data = load_sorted(os.path.join(DATA_DIR, info["file"]))
            peaks, troughs = zigzag(data, min_pct=min_pct)
            c_peaks, c_troughs = volume_confirm(data, peaks, troughs)
            results[key] = {
                "name": info["name"], "code": info["code"], "min_pct": min_pct,
                "peaks": [{k: v for k, v in p.items() if k != "idx"} for p in c_peaks],
                "troughs": [{k: v for k, v in t.items() if k != "idx"} for t in c_troughs],
                "all_peaks_idx": [p["idx"] for p in c_peaks],
                "all_troughs_idx": [t["idx"] for t in c_troughs],
            }
        total = sum(len(r["peaks"]) + len(r["troughs"]) for r in results.values())
        if 6 <= total <= 60:
            best_min_pct = min_pct
            break
        elif total < 6:
            best_min_pct = min_pct
            # continue trying smaller
        else:
            best_min_pct = min_pct - 2
            break
    else:
        best_min_pct = min_pct  # use last tried

    out_file = os.path.join(DATA_DIR, "swing_extrema.json")
    with open(out_file, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"波峰波谷分析完成: {out_file}")

    for key, r in results.items():
        print(f"\n{'='*55}")
        print(f"  {r['name']} ({r['code']})  min_pct={min_pct}%")
        print(f"{'='*55}")
        print(f"波峰卖出: {len(r['peaks'])} 个")
        for p in r["peaks"]:
            conf_icon = "🔴" if p["confidence"] == "强" else "🟡" if p["confidence"] == "中" else "⚪"
            print(f"  {conf_icon} {fmt(p['date'])} ¥{p['price']:.2f} [{p['confidence']}] {', '.join(p['reasons'])}")
        print(f"\n波谷买入: {len(r['troughs'])} 个")
        for t in r["troughs"]:
            conf_icon = "🟢" if t["confidence"] == "强" else "🟡" if t["confidence"] == "中" else "⚪"
            print(f"  {conf_icon} {fmt(t['date'])} ¥{t['price']:.2f} [{t['confidence']}] {', '.join(t['reasons'])}")

    return results


if __name__ == "__main__":
    main()
