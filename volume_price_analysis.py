#!/usr/bin/env python3
"""量价关系分析：中芯国际 + 兆易创新，识别阶段买卖点"""

import json, os, math

DATA_DIR = "/Users/gavin/WorkBuddy/AiQuant/data"
SYMBOLS = {
    "smic": {"name": "中芯国际", "code": "688981.SH", "file": "smic_daily.json"},
    "gigadevice": {"name": "兆易创新", "code": "603986.SH", "file": "gigadevice_daily.json"},
}

def calc_ma(values, n):
    result = []
    for i in range(len(values)):
        if i < n - 1:
            result.append(None)
        else:
            result.append(sum(values[i - n + 1 : i + 1]) / n)
    return result

def analyze(data, name):
    """分析量价关系，返回买卖点信号"""
    n = len(data)
    closes = [d["close"] for d in data]
    vols = [d["vol"] for d in data]
    opens = [d["open"] for d in data]
    highs = [d["high"] for d in data]
    lows = [d["low"] for d in data]
    trades = [d["trade_date"] for d in data]
    pct_chgs = [d["pct_chg"] for d in data]
    amounts = [d["amount"] for d in data]

    vol_ma5 = calc_ma(vols, 5)
    vol_ma20 = calc_ma(vols, 20)
    price_ma5 = calc_ma(closes, 5)
    price_ma20 = calc_ma(closes, 20)
    price_ma60 = calc_ma(closes, 60)

    buy_signals = []
    sell_signals = []
    annotations = []  # 关键量价事件

    for i in range(20, n - 1):  # 跳过前期，确保 MA 有效
        date = trades[i]
        close = closes[i]
        vol = vols[i]
        vol5 = vol_ma5[i] or 1
        vol20 = vol_ma20[i] or 1
        vol_ratio = vol / vol20 if vol20 else 1
        price5 = price_ma5[i]
        price20 = price_ma20[i]
        price60 = price_ma60[i]
        pct = pct_chgs[i]
        prev_close = closes[i - 1]
        prev_vol = vols[i - 1]

        # ===== 买入信号 =====
        buy_reasons = []

        # 1. 地量止跌：连续缩量 + 价格企稳 + 站上MA5
        if (vol_ratio < 0.5 and close > price5 and pct > 0
                and vols[i - 1] < vols[i - 2] and price_ma5[i - 1]):
            buy_reasons.append("地量企稳反弹")

        # 2. 倍量突破：成交量放大1.5倍+ 放量站上MA20 + 阳线
        if (vol_ratio > 1.5 and close > price20 and pct > 2
                and close > opens[i] and vol > vols[i - 1] * 1.3):
            buy_reasons.append("倍量突破关键均线")

        # 3. 缩量回调到支撑：缩量回踩MA20/MA60 + 收阳
        if (vol_ratio < 0.7 and pct > 0
                and abs(close - price20) / price20 < 0.03
                and close > prev_close):
            buy_reasons.append("缩量回踩支撑反弹")

        # 4. 底部放量反转：大跌后放大量收阳
        if (pct > 5 and vol_ratio > 1.8 and closes[i - 1] < price_ma20[i - 1]
                and closes[i - 2] < opens[i - 2] and closes[i - 3] < opens[i - 3]):
            buy_reasons.append("底部放量反转")

        if buy_reasons:
            buy_signals.append({
                "date": date,
                "idx": i,
                "price": close,
                "vol": vol,
                "vol_ratio": round(vol_ratio, 2),
                "pct_chg": pct,
                "reason": " | ".join(buy_reasons),
                "strength": len(buy_reasons),
            })

        # ===== 卖出信号 =====
        sell_reasons = []

        # 1. 天量滞涨：巨量但涨幅很小/收阴
        if vol_ratio > 2.0 and pct < 1.0 and close < opens[i]:
            sell_reasons.append("天量滞涨(放量收阴)")

        # 2. 高位放量长上影：冲高回落
        upper_shadow = (highs[i] - max(opens[i], close)) / max(opens[i], close)
        if upper_shadow > 0.05 and vol_ratio > 1.5 and (price60 and close > price60):
            sell_reasons.append("高位放量长上影")

        # 3. 连续放量后缩量：量能衰竭
        if (vol_ratio < 0.6 and vols[i - 1] > vol20 * 1.5
                and close < price5 and pct < 0):
            sell_reasons.append("爆量后缩量下跌(量能衰竭)")

        # 4. 跌破关键均线+放量
        if close < price20 and pct < -3 and vol_ratio > 1.3:
            sell_reasons.append("放量跌破MA20")

        if sell_reasons:
            sell_signals.append({
                "date": date,
                "idx": i,
                "price": close,
                "vol": vol,
                "vol_ratio": round(vol_ratio, 2),
                "pct_chg": pct,
                "reason": " | ".join(sell_reasons),
                "strength": len(sell_reasons),
            })

    # 合并相近信号（3天内同方向去重，保留最强的）
    def dedup(signals, gap=3):
        if not signals:
            return []
        result = []
        last = None
        for s in sorted(signals, key=lambda x: x["date"]):
            if last is None or int(s["date"]) - int(last["date"]) > gap:
                result.append(s)
                last = s
            elif s["strength"] > last["strength"]:
                result[-1] = s
                last = s
        return result

    buy_signals = dedup(buy_signals)
    sell_signals = dedup(sell_signals)

    return {
        "name": name,
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
        "total_days": n,
    }


def analyze_trend(data, signals):
    """识别阶段趋势"""
    closes = [d["close"] for d in data]
    price_ma20 = calc_ma(closes, 20)

    phases = []
    i = 0
    while i < len(data):
        if price_ma20[i] is None:
            i += 1
            continue
        # 找连续趋势段
        start = i
        trend = "up" if price_ma20[i] > (price_ma20[i - 1] or price_ma20[i]) else "down"
        j = i + 1
        while j < len(data) and price_ma20[j] is not None:
            new_trend = "up" if price_ma20[j] > price_ma20[j - 1] else "down" if price_ma20[j] < price_ma20[j - 1] else trend
            if new_trend != trend:
                # 至少持续10天才算阶段
                if j - start >= 10:
                    phases.append({
                        "start": data[start]["trade_date"],
                        "end": data[j - 1]["trade_date"],
                        "start_price": data[start]["close"],
                        "end_price": data[j - 1]["close"],
                        "change": round((data[j - 1]["close"] / data[start]["close"] - 1) * 100, 1),
                        "trend": trend,
                    })
                start = j
                trend = new_trend
            j += 1
        if j - start >= 10:
            phases.append({
                "start": data[start]["trade_date"],
                "end": data[j - 1]["trade_date"],
                "start_price": data[start]["close"],
                "end_price": data[j - 1]["close"],
                "change": round((data[j - 1]["close"] / data[start]["close"] - 1) * 100, 1),
                "trend": trend,
            })
        i = j
    return phases


def main():
    results = {}
    for key, info in SYMBOLS.items():
        with open(os.path.join(DATA_DIR, info["file"])) as f:
            raw = json.load(f)
        data = sorted(raw, key=lambda x: x["trade_date"])
        for d in data:
            d["open"] = float(d["open"])
            d["close"] = float(d["close"])
            d["high"] = float(d["high"])
            d["low"] = float(d["low"])
            d["vol"] = float(d["vol"])
            d["amount"] = float(d["amount"])
            d["pct_chg"] = float(d["pct_chg"])

        result = analyze(data, info["name"])
        phases = analyze_trend(data, result)
        result["phases"] = phases
        results[key] = result

        print(f"\n{'='*60}")
        print(f"  {info['name']} ({info['code']})  量价分析")
        print(f"{'='*60}")
        print(f"数据: {len(data)} 个交易日")

        # 阶段划分
        print(f"\n📊 阶段划分 (MA20 趋势):")
        for p in phases:
            emoji = "🔴" if p["trend"] == "up" else "🟢"
            print(f"  {emoji} {p['start']} ~ {p['end']}  收盘 {p['start_price']} → {p['end_price']}  ({p['change']:+.1f}%)")

        print(f"\n📈 量价买入信号 ({len(result['buy_signals'])} 个):")
        for s in result["buy_signals"][:8]:
            print(f"  {s['date']}  ¥{s['price']:.2f}  量比{s['vol_ratio']}  {s['reason']}")

        print(f"\n📉 量价卖出信号 ({len(result['sell_signals'])} 个):")
        for s in result["sell_signals"][:8]:
            print(f"  {s['date']}  ¥{s['price']:.2f}  量比{s['vol_ratio']}  {s['reason']}")

    # 保存分析结果
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "volume_price_analysis.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n分析结果已保存: {DATA_DIR}/volume_price_analysis.json")

if __name__ == "__main__":
    main()
