#!/usr/bin/env python3
"""
主力行为分析 & 波段操作建议
基于量价关系识别：主力吸筹 / 洗盘 / 拉升 / 出货 四个阶段
"""

import json, os, math
from dataclasses import dataclass, field
from typing import List, Dict, Optional

DATA_DIR = "/Users/gavin/WorkBuddy/AiQuant/data"
OUT_DIR = "/Users/gavin/WorkBuddy/AiQuant/outputs"

SYMBOLS = {
    "smic": {"name": "中芯国际", "code": "688981.SH", "file": "smic_daily.json"},
    "gigadevice": {"name": "兆易创新", "code": "603986.SH", "file": "gigadevice_daily.json"},
}


@dataclass
class DayData:
    date: str
    open: float
    close: float
    high: float
    low: float
    vol: float
    amount: float
    pct_chg: float


def load_data(filepath) -> List[DayData]:
    with open(filepath) as f:
        raw = json.load(f)
    data = sorted(raw, key=lambda x: x["trade_date"])
    return [
        DayData(
            date=d["trade_date"],
            open=float(d["open"]),
            close=float(d["close"]),
            high=float(d["high"]),
            low=float(d["low"]),
            vol=float(d["vol"]),
            amount=float(d["amount"]),
            pct_chg=float(d["pct_chg"]),
        )
        for d in data
    ]


def sma(values, n):
    """简单移动平均"""
    r = []
    for i in range(len(values)):
        if i < n - 1:
            r.append(None)
        else:
            r.append(sum(values[i - n + 1 : i + 1]) / n)
    return r


def main_force_analysis(data: List[DayData], name: str, code: str):
    """主力行为深度分析"""
    n = len(data)
    closes = [d.close for d in data]
    vols = [d.vol for d in data]
    amounts = [d.amount for d in data]
    opens = [d.open for d in data]
    highs = [d.high for d in data]
    lows = [d.low for d in data]

    ma5 = sma(closes, 5)
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    vol_ma5 = sma(vols, 5)
    vol_ma20 = sma(vols, 20)
    vol_ma60 = sma(vols, 60)

    # 振幅
    amplitudes = []
    for i in range(n):
        prev = closes[i - 1] if i > 0 else opens[i]
        amplitudes.append((highs[i] - lows[i]) / prev * 100)

    # ===== 主力介入指标 =====
    main_force_days = []
    accumulation_zones = []
    distribution_zones = []
    shakeout_days = []
    pump_days = []

    for i in range(20, n - 1):
        vol = vols[i]
        vol5 = vol_ma5[i] or 1
        vol20 = vol_ma20[i] or 1
        vol60 = vol_ma60[i] or 1
        vol_ratio5 = vol / vol5
        vol_ratio20 = vol / vol20

        close = closes[i]
        amp = amplitudes[i]
        body = abs(close - opens[i])
        upper_shadow = highs[i] - max(close, opens[i])
        lower_shadow = min(close, opens[i]) - lows[i]

        # ----- 吸筹信号 (Accumulation) -----
        acc_score = 0
        acc_reasons = []

        # 1. 低位地量小阴小阳（主力暗中吸筹）
        if vol_ratio20 < 0.5 and amp < 3 and abs(data[i].pct_chg) < 2:
            acc_score += 2
            acc_reasons.append("地量窄幅整理(疑似吸筹)")

        # 2. 连续3日以上缩量横盘后突然放量阳线（结束吸筹，准备拉升）
        if (vol_ratio20 > 1.8 and data[i].pct_chg > 3 and close > opens[i]
                and all(vols[i - j] < vol_ma20[i - j] * 0.7 for j in range(1, 4) if i - j >= 0 and vol_ma20[i - j])):
            acc_score += 3
            acc_reasons.append("缩量整理后倍量突破(吸筹结束信号)")

        # 3. 低位大量换手但价格不跌（主力对倒吸筹）
        if vol_ratio20 > 1.5 and amp > 4 and abs(data[i].pct_chg) < 1.5 and (ma60[i] and close < ma60[i] * 1.1):
            acc_score += 2
            acc_reasons.append("低位高换手滞跌(主力接筹)")

        if acc_score >= 3:
            accumulation_zones.append({
                "date": data[i].date,
                "price": round(close, 2),
                "vol_ratio": round(vol_ratio20, 2),
                "reasons": acc_reasons,
                "score": acc_score,
            })

        # ----- 洗盘信号 (Shakeout) -----
        wash_score = 0
        wash_reasons = []

        # 1. 缩量急跌（清洗浮筹）
        if data[i].pct_chg < -3 and vol_ratio20 < 0.6 and (ma60[i] and close > ma60[i]):
            wash_score += 3
            wash_reasons.append("缩量急跌(典型洗盘)")

        # 2. 放量下影线（盘中打压后收回）
        if lower_shadow / (close if close else 1) > 0.03 and vol_ratio20 > 1.2 and body < lower_shadow:
            wash_score += 2
            wash_reasons.append("放量长下影(V型洗盘)")

        if wash_score >= 3:
            shakeout_days.append({
                "date": data[i].date,
                "price": round(close, 2),
                "reasons": wash_reasons,
                "score": wash_score,
            })

        # ----- 拉升信号 (Pump/Rally) -----
        pump_score = 0
        pump_reasons = []

        # 1. 倍量长阳突破（主力主动拉升）
        if vol_ratio20 > 1.8 and data[i].pct_chg > 5 and close > ma20[i]:
            pump_score += 3
            pump_reasons.append("倍量长阳突破(主力拉升)")

        # 2. 连续温和放量上涨（推土机式拉升）
        if (all(vols[i - j] > vols[i - j - 1] * 0.9 for j in range(3) if i - j - 1 >= 0)
                and all(data[i - j].pct_chg > 0 for j in range(4))
                and close > ma20[i]):
            pump_score += 2
            pump_reasons.append("连续温和放量上涨(推土机拉升)")

        # 3. 跳空高开放量（强势拉升）
        if opens[i] > highs[i - 1] * 1.005 and vol_ratio20 > 1.5 and data[i].pct_chg > 3:
            pump_score += 2
            pump_reasons.append("跳空放量高开(强势突破)")

        if pump_score >= 3:
            pump_days.append({
                "date": data[i].date,
                "price": round(close, 2),
                "reasons": pump_reasons,
                "score": pump_score,
            })

        # ----- 出货信号 (Distribution) -----
        dist_score = 0
        dist_reasons = []

        # 1. 天量滞涨（高位放量不涨）
        if vol_ratio20 > 2.5 and abs(data[i].pct_chg) < 1.5 and (ma60[i] and close > ma60[i]):
            dist_score += 3
            dist_reasons.append("天量滞涨(主力出货)")

        # 2. 高位放量长上影（拉高出货）
        if upper_shadow / close > 0.05 and vol_ratio20 > 1.5 and (ma60[i] and close > ma60[i] * 1.2):
            dist_score += 3
            dist_reasons.append("高位放量长上影(拉高出货)")

        # 3. 连续放量后突然缩量下跌（出货完成）
        if (data[i].pct_chg < -2 and vol_ratio20 < 0.6
                and vols[i - 1] > vol_ma20[i - 1] * 1.5 and vols[i - 2] > vol_ma20[i - 2] * 1.5):
            dist_score += 2
            dist_reasons.append("连续放量后缩量下跌(出货完成)")

        if dist_score >= 3:
            distribution_zones.append({
                "date": data[i].date,
                "price": round(close, 2),
                "vol_ratio": round(vol_ratio20, 2),
                "reasons": dist_reasons,
                "score": dist_score,
            })

    # ===== 波段操作建议 =====
    swing_signals = generate_swing_signals(data, ma5, ma20, ma60, vol_ma5, vol_ma20, amplitudes)

    # ===== 主力力度评估 =====
    force_level = assess_main_force(accumulation_zones, pump_days, distribution_zones, shakeout_days, n)

    return {
        "name": name,
        "code": code,
        "total_days": n,
        "main_force_assessment": force_level,
        "accumulation": accumulation_zones[:10],
        "pump_signals": pump_days[:10],
        "distribution": distribution_zones[:10],
        "shakeout": shakeout_days[:8],
        "swing_signals": swing_signals,
    }


def generate_swing_signals(data, ma5, ma20, ma60, vol_ma5, vol_ma20, amps):
    """生成波段买卖操作建议"""
    n = len(data)
    closes = [d.close for d in data]
    vols = [d.vol for d in data]
    signals = []
    position = None  # None=空仓, "long"=持仓
    entry_price = 0

    for i in range(30, n):
        close = closes[i]
        m5 = ma5[i]; m20 = ma20[i]; m60 = ma60[i]
        if m5 is None or m20 is None or m60 is None:
            continue
        vol = vols[i]
        v20 = vol_ma20[i] or 1

        # 空仓 → 开仓买入
        if position is None:
            buy_signal = False
            buy_reason = ""

            # 1. 缩量回踩MA20 + 收阳
            if (abs(close - m20) / m20 < 0.02 and data[i].pct_chg > 0
                    and vol < v20 and amps[i] < 3.5):
                buy_signal = True
                buy_reason = "缩量回踩MA20支撑"

            # 2. 倍量站上MA5 + MA5>MA20金叉
            elif (vol > v20 * 1.5 and close > m5 and m5 > m20
                    and data[i].pct_chg > 2):
                buy_signal = True
                buy_reason = "倍量突破+均线金叉"

            # 3. 地量后放量阳线（底部反转）
            elif (vol > v20 * 1.3 and data[i].pct_chg > 3
                    and all(vol_ma20[i - j] and vols[i - j] < vol_ma20[i - j] * 0.5 for j in range(1, 5) if i - j >= 0)):
                buy_signal = True
                buy_reason = "地量后放量反转"

            # 4. 回踩MA60不破 + 缩量
            elif (abs(close - m60) / m60 < 0.03 and data[i].pct_chg > 0
                    and vol < v20 * 0.7 and amps[i] < 3):
                buy_signal = True
                buy_reason = "缩量回踩MA60强支撑"

            if buy_signal:
                entry_price = close
                position = "long"
                # 止损价
                stop_loss = round(min(low_support(data, i), entry_price * 0.93), 2)
                signals.append({
                    "date": data[i].date,
                    "action": "BUY",
                    "action_cn": "📈 波段买入",
                    "price": round(close, 2),
                    "reason": buy_reason,
                    "stop_loss": stop_loss,
                    "targets": [
                        round(entry_price * 1.05, 2),
                        round(entry_price * 1.10, 2),
                        round(entry_price * 1.15, 2),
                    ],
                })

        # 持仓 → 卖出
        else:
            sell_signal = False
            sell_reason = ""
            profit = (close / entry_price - 1) * 100

            # 止盈策略
            # 1. 天量滞涨（放量不涨）
            if vol > v20 * 2.5 and abs(data[i].pct_chg) < 1 and profit > 3:
                sell_signal = True
                sell_reason = f"天量滞涨(+{profit:.1f}%)"

            # 2. 高位放量长上影
            upper_shadow = data[i].high - max(data[i].close, data[i].open)
            if upper_shadow / close > 0.04 and vol > v20 * 1.5 and profit > 5:
                sell_signal = True
                sell_reason = f"高位放量长上影(+{profit:.1f}%)"

            # 3. 跌破MA20 + 放量
            elif close < m20 and data[i].pct_chg < -2 and vol > v20:
                sell_signal = True
                sell_reason = f"放量跌破MA20(+{profit:.1f}%)"

            # 4. 连续大涨后缩量（涨幅>15%，考虑止盈）
            elif profit > 15 and vol < v20 * 0.5 and data[i].pct_chg < 0:
                sell_signal = True
                sell_reason = f"大涨后缩量回落(+{profit:.1f}%)"

            # 5. 止损
            stop_loss_price = entry_price * 0.93
            if close < stop_loss_price:
                sell_signal = True
                sell_reason = f"止损触发({(close/entry_price-1)*100:.1f}%)"

            if sell_signal:
                signals.append({
                    "date": data[i].date,
                    "action": "SELL",
                    "action_cn": "📉 波段卖出",
                    "price": round(close, 2),
                    "profit_pct": round(profit, 1),
                    "reason": sell_reason,
                    "entry_price": round(entry_price, 2),
                })
                position = None
                entry_price = 0

    # 如果当前持仓，给出持有建议
    current_advice = None
    if position == "long" and signals:
        last_close = closes[-1]
        profit = (last_close / entry_price - 1) * 100
        current_advice = {
            "status": "holding",
            "entry_date": signals[-1]["date"],
            "entry_price": entry_price,
            "current_price": round(last_close, 2),
            "profit_pct": round(profit, 1),
            "suggestion": "继续持有" if profit > 0 else "注意风险",
            "stop_loss": round(entry_price * 0.93, 2),
            "next_target": round(entry_price * 1.10, 2) if profit < 10 else round(entry_price * 1.15, 2),
        }

    return {
        "signals": signals,
        "current_position": current_advice,
    }


def low_support(data, idx):
    """计算近期支撑位（20日最低）"""
    start = max(0, idx - 20)
    return min(d.low for d in data[start:idx + 1])


def assess_main_force(acc, pump, dist, wash, total_days):
    """评估主力介入程度"""
    acc_count = len(acc)
    pump_count = len(pump)
    dist_count = len(dist)
    wash_count = len(wash)

    # 主力活跃度 = (吸筹+拉升+洗盘信号) / 总交易日
    activity_ratio = (acc_count + pump_count + wash_count) / total_days * 100

    level = "微弱"
    desc = ""
    if activity_ratio > 8:
        level = "非常活跃"
        desc = "主力深度介入，操作痕迹明显，吸筹/拉升/洗盘信号密集"
    elif activity_ratio > 5:
        level = "较活跃"
        desc = "主力中度参与，有明显波段运作特征"
    elif activity_ratio > 2.5:
        level = "一般"
        desc = "有一定主力活动，但信号不够密集"
    else:
        level = "微弱"
        desc = "主力介入迹象不明显，走势偏自然/散户化"

    # 出货占比
    total_ops = acc_count + pump_count + dist_count + wash_count
    dist_ratio = dist_count / total_ops * 100 if total_ops > 0 else 0

    return {
        "level": level,
        "description": desc,
        "activity_ratio": round(activity_ratio, 1),
        "accumulation_signals": acc_count,
        "pump_signals": pump_count,
        "distribution_signals": dist_count,
        "shakeout_signals": wash_count,
        "distribution_ratio": round(dist_ratio, 1),
        "risk_note": "出货信号占比较高，注意高位风险" if dist_ratio > 20 else "出货信号较少，主力控盘较好",
    }


def fmt_date(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def main():
    results = {}
    for key, info in SYMBOLS.items():
        data = load_data(os.path.join(DATA_DIR, info["file"]))
        result = main_force_analysis(data, info["name"], info["code"])
        results[key] = result

    # 保存结果
    out_file = os.path.join(DATA_DIR, "main_force_analysis.json")
    # 简化序列化
    simplified = {}
    for key, r in results.items():
        simplified[key] = {
            "name": r["name"],
            "code": r["code"],
            "total_days": r["total_days"],
            "main_force_assessment": r["main_force_assessment"],
            "accumulation": r["accumulation"],
            "pump_signals": r["pump_signals"],
            "distribution": r["distribution"],
            "shakeout": r["shakeout"],
            "swing_signals": r["swing_signals"],
        }
    with open(out_file, "w") as f:
        json.dump(simplified, f, ensure_ascii=False, indent=2)
    print(f"分析结果保存: {out_file}")

    # 打印摘要
    for key, r in results.items():
        f = r["main_force_assessment"]
        sw = r["swing_signals"]
        print(f"\n{'='*65}")
        print(f"  {r['name']} ({r['code']})  主力行为 & 波段分析")
        print(f"{'='*65}")
        print(f"主力活跃度: {f['level']} (活跃指数 {f['activity_ratio']}%)")
        print(f"  {f['description']}")
        print(f"  吸筹: {f['accumulation_signals']} | 洗盘: {f['shakeout_signals']} | 拉升: {f['pump_signals']} | 出货: {f['distribution_signals']}")
        print(f"  {f['risk_note']}")

        print(f"\n📊 波段操作信号 ({len(sw['signals'])} 次):")
        for s in sw["signals"][-8:]:
            emoji = "🔴" if s["action"] == "BUY" else "🟢"
            extra = ""
            if s["action"] == "BUY":
                extra = f"  止损: ¥{s['stop_loss']}  目标: ¥{s['targets'][0]}→¥{s['targets'][2]}"
            else:
                extra = f"  收益: {s['profit_pct']:+.1f}%  入场: ¥{s['entry_price']}"
            print(f"  {emoji} {fmt_date(s['date'])}  ¥{s['price']:.2f}  {s['reason']}{extra}")

        if sw["current_position"]:
            cp = sw["current_position"]
            print(f"\n📍 当前持仓: 入场 ¥{cp['entry_price']}  现价 ¥{cp['current_price']}  ({cp['profit_pct']:+.1f}%)")
            print(f"  止损: ¥{cp['stop_loss']}  下一目标: ¥{cp['next_target']}  建议: {cp['suggestion']}")


if __name__ == "__main__":
    main()
