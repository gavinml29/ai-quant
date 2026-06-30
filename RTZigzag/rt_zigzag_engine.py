"""
RTZigzag 核心引擎 - 三级确认系统

Level 1: 实时量价预警（前瞻性，盘中即可触发）
Level 2: 分钟级 Zigzag 结构确认（滞后2-4小时）
Level 3: 日线级别趋势验证（次日确认）

只有多级共振时给出高置信度信号
"""

import json
import os
from datetime import datetime
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DAILY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_30min(key):
    """加载30分钟K线数据"""
    path = os.path.join(DATA_DIR, f"{key}_30min.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    # 确保按时间排序（旧→新）
    data.sort(key=lambda x: x["trade_time"])
    return data


def load_daily(key):
    """加载日线数据"""
    path = os.path.join(DAILY_DIR, f"{key}_daily.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    data.sort(key=lambda x: x["trade_date"])
    return data


# ============================================================
# Level 2: 分钟级 Zigzag 极值点检测
# ============================================================

def calc_ma(values, period):
    """计算移动平均"""
    result = []
    for i in range(len(values)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(values[i-period+1:i+1]) / period)
    return result


def zigzag_30min(data, min_pct=2.0, lookback=5):
    """
    30分钟级 Zigzag 检测
    - min_pct: 最小涨跌幅阈值（30分钟级别用2%）
    - lookback: 前后各看几根K线（5根 = 2.5小时）

    返回: peaks, troughs
    """
    n = len(data)
    if n < lookback * 2 + 1:
        return [], []

    # 找所有局部极值
    raw_extremes = []

    for i in range(lookback, n - lookback):
        high = data[i]["high"]
        low = data[i]["low"]

        # 波峰判定
        is_peak = all(data[i-j]["high"] <= high for j in range(1, lookback+1)) and \
                  all(data[i+j]["high"] <= high for j in range(1, lookback+1))

        # 波谷判定
        is_trough = all(data[i-j]["low"] >= low for j in range(1, lookback+1)) and \
                    all(data[i+j]["low"] >= low for j in range(1, lookback+1))

        if is_peak:
            raw_extremes.append({
                "idx": i, "type": "peak", "price": high,
                "time": data[i]["trade_time"],
                "close": data[i]["close"], "vol": data[i]["vol"]
            })
        if is_trough:
            raw_extremes.append({
                "idx": i, "type": "trough", "price": low,
                "time": data[i]["trade_time"],
                "close": data[i]["close"], "vol": data[i]["vol"]
            })

    # 合并 + 去重 + 幅度过滤
    raw_extremes.sort(key=lambda x: x["idx"])
    filtered = []
    last = None

    for ext in raw_extremes:
        if last is None:
            filtered.append(ext)
            last = ext
            continue

        # 同类型，取更极端的
        if ext["type"] == last["type"]:
            if ext["type"] == "peak" and ext["price"] > last["price"]:
                filtered[-1] = ext
                last = ext
            elif ext["type"] == "trough" and ext["price"] < last["price"]:
                filtered[-1] = ext
                last = ext
            continue

        # 类型切换，检查幅度
        change = abs(ext["price"] - last["price"]) / last["price"] * 100
        if change >= min_pct:
            filtered.append(ext)
            last = ext

    peaks = [e for e in filtered if e["type"] == "peak"]
    troughs = [e for e in filtered if e["type"] == "trough"]

    return peaks, troughs


# ============================================================
# Level 1: 实时量价预警引擎
# ============================================================

def volume_price_alerts(data_30min, lookback_vol=16):
    """
    实时量价预警（基于30分钟K线）
    - lookback_vol: 均量计算窗口（16根30分钟 = 约4个交易日）

    返回预警信号列表
    """
    n = len(data_30min)
    if n < lookback_vol + 5:
        return []

    alerts = []

    # 计算均量
    vols = [d["vol"] for d in data_30min]
    closes = [d["close"] for d in data_30min]

    # MA计算
    ma5 = calc_ma(closes, 10)   # 10根30分钟 ≈ 半天
    ma20 = calc_ma(closes, 40)  # 40根30分钟 ≈ 2天

    for i in range(lookback_vol, n):
        vol = data_30min[i]["vol"]
        close = data_30min[i]["close"]
        open_ = data_30min[i]["open"]
        high = data_30min[i]["high"]
        low = data_30min[i]["low"]
        pct_chg = (close - data_30min[i-1]["close"]) / data_30min[i-1]["close"] * 100 if i > 0 else 0

        # 均量
        avg_vol = sum(vols[i-lookback_vol:i]) / lookback_vol
        vol_ratio = vol / avg_vol if avg_vol > 0 else 1.0

        # 振幅
        amplitude = (high - low) / close * 100 if close > 0 else 0

        # 上下影线
        body = abs(close - open_)
        upper_shadow = high - max(close, open_)
        lower_shadow = min(close, open_) - low

        time_str = data_30min[i]["trade_time"]

        # --- 买入预警 ---

        # 1. 缩量回踩MA20
        if ma20[i] and abs(close - ma20[i]) / ma20[i] < 0.02 and vol_ratio < 0.7:
            alerts.append({
                "time": time_str, "type": "BUY",
                "signal": "缩量回踩支撑",
                "desc": f"价格触及MA20({ma20[i]:.2f})，量比{vol_ratio:.2f}，缩量明显",
                "strength": 2, "vol_ratio": round(vol_ratio, 2)
            })

        # 2. 放量突破MA20
        if ma20[i] and data_30min[i-1]["close"] < ma20[i] and close > ma20[i] and vol_ratio > 1.5:
            alerts.append({
                "time": time_str, "type": "BUY",
                "signal": "放量突破MA20",
                "desc": f"突破MA20({ma20[i]:.2f})，量比{vol_ratio:.2f}，放量突破",
                "strength": 3, "vol_ratio": round(vol_ratio, 2)
            })

        # 3. 底部放量反弹（跌后放量收阳）
        if close > open_ and vol_ratio > 2.0 and pct_chg > 1.5:
            # 检查前5根是否有明显下跌
            if i >= 5 and closes[i-5] > close * 1.03:
                alerts.append({
                    "time": time_str, "type": "BUY",
                    "signal": "底部放量反弹",
                    "desc": f"放量{vol_ratio:.1f}x收阳{pct_chg:.1f}%，前5根跌幅明显",
                    "strength": 3, "vol_ratio": round(vol_ratio, 2)
                })

        # 4. 长下影线+放量（资金接筹）
        if lower_shadow > body * 2 and vol_ratio > 1.3:
            alerts.append({
                "time": time_str, "type": "BUY",
                "signal": "长下影放量承接",
                "desc": f"下影线{lower_shadow:.2f}，量比{vol_ratio:.2f}，低位有承接",
                "strength": 2, "vol_ratio": round(vol_ratio, 2)
            })

        # --- 卖出预警 ---

        # 5. 放量滞涨
        if vol_ratio > 2.0 and abs(pct_chg) < 0.5:
            alerts.append({
                "time": time_str, "type": "SELL",
                "signal": "放量滞涨",
                "desc": f"量比{vol_ratio:.2f}但涨幅仅{pct_chg:.2f}%，高位放量需警惕",
                "strength": 3, "vol_ratio": round(vol_ratio, 2)
            })

        # 6. 天量长上影
        if upper_shadow > body * 1.5 and vol_ratio > 1.8:
            alerts.append({
                "time": time_str, "type": "SELL",
                "signal": "天量长上影",
                "desc": f"上影线{upper_shadow:.2f}，量比{vol_ratio:.2f}，抛压明显",
                "strength": 2, "vol_ratio": round(vol_ratio, 2)
            })

        # 7. 放量跌破MA20
        if ma20[i] and data_30min[i-1]["close"] > ma20[i] and close < ma20[i] and vol_ratio > 1.5:
            alerts.append({
                "time": time_str, "type": "SELL",
                "signal": "放量跌破MA20",
                "desc": f"跌破MA20({ma20[i]:.2f})，量比{vol_ratio:.2f}，放量破位",
                "strength": 3, "vol_ratio": round(vol_ratio, 2)
            })

        # 8. 量价背离（价格创新高但量能萎缩）
        if i >= 20:
            recent_high = max(closes[i-20:i])
            recent_max_vol = max(vols[i-20:i])
            if close > recent_high * 0.99 and vol < recent_max_vol * 0.7:
                alerts.append({
                    "time": time_str, "type": "SELL",
                    "signal": "量价背离",
                    "desc": f"价格接近前高但量能仅{vol/recent_max_vol*100:.0f}%，顶背离",
                    "strength": 2, "vol_ratio": round(vol_ratio, 2)
                })

    return alerts


# ============================================================
# Level 3: 日线趋势验证
# ============================================================

def daily_trend_check(daily_data, ref_date):
    """
    检查日线级别的趋势是否支持当前信号
    返回: trend ("UP"/"DOWN"/"RANGE"), ma5, ma20, ma60
    """
    if len(daily_data) < 60:
        return {"trend": "UNKNOWN"}, None, None, None

    # 找到最接近 ref_date 的日线
    ref_str = ref_date[:10].replace("-", "")
    idx = None
    for i, d in enumerate(daily_data):
        if d["trade_date"] <= ref_str:
            idx = i

    if idx is None or idx < 60:
        return {"trend": "UNKNOWN"}, None, None, None

    closes = [float(d["close"]) for d in daily_data[:idx+1]]
    ma5 = sum(closes[-5:]) / 5
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60

    # 趋势判断
    if ma5 > ma20 > ma60:
        trend = "UP"
    elif ma5 < ma20 < ma60:
        trend = "DOWN"
    else:
        trend = "RANGE"

    return {"trend": trend, "ma5": round(ma5, 2), "ma20": round(ma20, 2), "ma60": round(ma60, 2)}, ma5, ma20, ma60


# ============================================================
# 三级共振匹配
# ============================================================

def resonance_match(peaks, troughs, alerts, daily_data, max_gap_hours=4):
    """
    三级信号共振匹配

    匹配逻辑：
    - 在 Zigzag 极值点附近 ±4小时 内出现的量价预警信号
    - 且日线趋势方向吻合

    返回高置信度买卖信号
    """
    signals = []

    def time_to_dt(t):
        return datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S")

    # 波谷 + 买入预警共振
    for trough in troughs:
        trough_time = time_to_dt(trough["time"])
        matched_alerts = []

        for alert in alerts:
            if alert["type"] != "BUY":
                continue
            alert_time = time_to_dt(alert["time"])
            gap_hours = abs((alert_time - trough_time).total_seconds()) / 3600
            if gap_hours <= max_gap_hours:
                matched_alerts.append(alert)

        # 日线趋势
        trend_info, _, _, _ = daily_trend_check(daily_data, trough["time"])

        # 共振强度
        if matched_alerts:
            max_strength = max(a["strength"] for a in matched_alerts)
            alert_count = len(matched_alerts)
        else:
            max_strength = 0
            alert_count = 0

        # 趋势加分
        trend_bonus = 1 if trend_info["trend"] == "UP" else 0

        confidence = min(5, max_strength + (1 if alert_count >= 2 else 0) + trend_bonus)

        signals.append({
            "type": "BUY",
            "zigzag_point": {
                "time": trough["time"],
                "price": round(trough["price"], 2),
                "vol": trough["vol"]
            },
            "matched_alerts": matched_alerts,
            "daily_trend": trend_info["trend"],
            "confidence": confidence,
            "confidence_label": {0: "·", 1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}.get(confidence, "·"),
            "desc": _build_signal_desc("BUY", trough, matched_alerts, trend_info)
        })

    # 波峰 + 卖出预警共振
    for peak in peaks:
        peak_time = time_to_dt(peak["time"])
        matched_alerts = []

        for alert in alerts:
            if alert["type"] != "SELL":
                continue
            alert_time = time_to_dt(alert["time"])
            gap_hours = abs((alert_time - peak_time).total_seconds()) / 3600
            if gap_hours <= max_gap_hours:
                matched_alerts.append(alert)

        trend_info, _, _, _ = daily_trend_check(daily_data, peak["time"])

        if matched_alerts:
            max_strength = max(a["strength"] for a in matched_alerts)
            alert_count = len(matched_alerts)
        else:
            max_strength = 0
            alert_count = 0

        trend_bonus = 1 if trend_info["trend"] == "DOWN" else 0
        confidence = min(5, max_strength + (1 if alert_count >= 2 else 0) + trend_bonus)

        signals.append({
            "type": "SELL",
            "zigzag_point": {
                "time": peak["time"],
                "price": round(peak["price"], 2),
                "vol": peak["vol"]
            },
            "matched_alerts": matched_alerts,
            "daily_trend": trend_info["trend"],
            "confidence": confidence,
            "confidence_label": {0: "·", 1: "⭐", 2: "⭐⭐", 3: "⭐⭐⭐", 4: "⭐⭐⭐⭐", 5: "⭐⭐⭐⭐⭐"}.get(confidence, "·"),
            "desc": _build_signal_desc("SELL", peak, matched_alerts, trend_info)
        })

    # 按时间排序
    signals.sort(key=lambda s: s["zigzag_point"]["time"])

    return signals


def _build_signal_desc(sig_type, zigzag_point, alerts, trend_info):
    """构建信号描述文本"""
    parts = []
    if alerts:
        alert_names = list(set(a["signal"] for a in alerts))
        parts.append(f"量价确认: {'+'.join(alert_names)}")
    else:
        parts.append("量价确认: 无共振")

    parts.append(f"日线趋势: {trend_info['trend']}")

    if sig_type == "BUY":
        parts.append("→ 波谷结构形成" if alerts else "→ 波谷待确认")
    else:
        parts.append("→ 波峰结构形成" if alerts else "→ 波峰待确认")

    return " | ".join(parts)


# ============================================================
# 主分析入口
# ============================================================

STOCKS = [
    {"key": "smic",       "code": "688981.SH", "name": "中芯国际"},
    {"key": "gigadevice", "code": "603986.SH", "name": "兆易创新"},
    {"key": "goldwind",   "code": "002202.SZ", "name": "金风科技"},
    {"key": "bright",     "code": "688333.SH", "name": "铂力特"},
    {"key": "leader",     "code": "688017.SH", "name": "绿的谐波"},
    {"key": "siruixin",   "code": "688102.SH", "name": "斯瑞新材"},
    {"key": "montage",    "code": "688008.SH", "name": "澜起科技"},
]


def analyze_all():
    """分析所有股票"""
    results = {}

    for stock in STOCKS:
        key = stock["key"]
        print(f"\n{'='*60}")
        print(f"分析 {stock['name']} ({stock['code']})")
        print(f"{'='*60}")

        data_30min = load_30min(key)
        daily_data = load_daily(key)

        if not data_30min:
            print(f"  ❌ 无30分钟数据")
            continue

        print(f"  30分钟数据: {len(data_30min)} 条")
        print(f"  时间范围: {data_30min[0]['trade_time'][:16]} ~ {data_30min[-1]['trade_time'][:16]}")

        # Level 2: Zigzag
        peaks, troughs = zigzag_30min(data_30min, min_pct=2.0, lookback=5)
        print(f"  Zigzag: {len(peaks)} 波峰, {len(troughs)} 波谷")

        # Level 1: 量价预警
        alerts = volume_price_alerts(data_30min)
        buy_alerts = [a for a in alerts if a["type"] == "BUY"]
        sell_alerts = [a for a in alerts if a["type"] == "SELL"]
        print(f"  量价预警: {len(buy_alerts)} 买入, {len(sell_alerts)} 卖出")

        # Level 3: 共振匹配
        signals = resonance_match(peaks, troughs, alerts, daily_data)
        high_conf = [s for s in signals if s["confidence"] >= 3]
        print(f"  共振信号: {len(signals)} 总计, {len(high_conf)} 高置信度(≥3⭐)")

        # 最新信号
        if signals:
            latest = signals[-1]
            print(f"  最新信号: {latest['type']} @ {latest['zigzag_point']['time'][:16]} "
                  f"¥{latest['zigzag_point']['price']} {latest['confidence_label']}")

        results[key] = {
            "name": stock["name"], "code": stock["code"],
            "data_count": len(data_30min),
            "time_range": [data_30min[0]["trade_time"], data_30min[-1]["trade_time"]],
            "peaks": peaks, "troughs": troughs,
            "alerts": alerts,
            "signals": signals,
            "daily_trend": daily_trend_check(daily_data, data_30min[-1]["trade_time"])[0] if daily_data else "N/A",
        }

    return results


if __name__ == "__main__":
    results = analyze_all()

    # 保存结果
    out_path = os.path.join(DATA_DIR, "rt_zigzag_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"结果已保存到 {out_path}")
    print(f"{'='*60}")
