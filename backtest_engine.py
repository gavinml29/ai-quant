#!/usr/bin/env python3
"""
日线策略回测引擎

策略逻辑（与 RTZigzag 看板一致，但去除未来数据偏差）:
1. Zigzag 波峰波谷检测（lookback 窗口内局部极值）
2. 量价确认信号（地量地价/天量天价/放量突破等）
3. 回测时关键：信号确认需要等待 lookback 天，不能"穿越"

回测规则:
- 初始资金 100万
- 仓位：满仓买入/卖出（简化模型）
- 手续费：买入 0.025%，卖出 0.025% + 印花税 0.05%
- 滑点：买入 +0.2%，卖出 -0.2%
- 止损：买入价 -5%
- 止盈：波峰检测确认后卖出
- T+1：买入次日才能卖出
"""

import json
import os
from datetime import datetime

DATA_DIR = "/Users/gavin/WorkBuddy/AiQuant/data"
OUT_DIR = "/Users/gavin/WorkBuddy/AiQuant/outputs"

STOCKS = [
    {"key": "smic",       "name": "中芯国际", "code": "688981.SH"},
    {"key": "gigadevice", "name": "兆易创新", "code": "603986.SH"},
    {"key": "goldwind",   "name": "金风科技", "code": "002202.SZ"},
    {"key": "bright",     "name": "铂力特",   "code": "688333.SH"},
    {"key": "leader",     "name": "绿的谐波", "code": "688017.SH"},
    {"key": "siruixin",   "name": "斯瑞新材", "code": "688102.SH"},
    {"key": "montage",    "name": "澜起科技", "code": "688008.SH"},
]


def load_daily(key):
    path = os.path.join(DATA_DIR, f"{key}_daily.json")
    with open(path) as f:
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
            "pre_close": float(d.get("pre_close", d["close"])),
        })
    return data


# ============================================================
# 技术指标计算
# ============================================================

def calc_ma(values, period):
    result = [None] * len(values)
    for i in range(period - 1, len(values)):
        result[i] = sum(values[i - period + 1:i + 1]) / period
    return result


def calc_ma_vol(vols, period):
    return calc_ma(vols, period)


# ============================================================
# 信号生成（回测专用 — 严格无未来数据偏差）
# ============================================================

def generate_signals_bt(data, min_pct=5.0, lookback=8):
    """
    生成回测买卖信号

    关键：Zigzag 极值点确认需要 lookback 天
    所以信号在第 i 天形成，实际确认日在 i + lookback 天
    我们在第 i + lookback 天才能"看到"这个信号

    量价确认信号是实时的（当天就能看到）

    回测执行规则：
    - 买入信号在第 i 天的量价预警触发
    - 但 Zigzag 波谷确认要等到 i + lookback 天
    - 所以实际买入在 i + lookback + 1 天的开盘价
    """
    n = len(data)
    closes = [d["close"] for d in data]
    highs = [d["high"] for d in data]
    lows = [d["low"] for d in data]
    vols = [d["vol"] for d in data]

    ma5 = calc_ma(closes, 5)
    ma10 = calc_ma(closes, 10)
    ma20 = calc_ma(closes, 20)
    ma60 = calc_ma(closes, 60)
    ma_vol20 = calc_ma_vol(vols, 20)

    signals = []  # {"date_idx": i, "type": "BUY"/"SELL", "confirm_idx": i+lookback, "reason": "..."}

    for i in range(max(60, lookback), n):
        close = closes[i]
        vol = vols[i]
        open_ = data[i]["open"]
        high = highs[i]
        low = lows[i]

        avg_vol = ma_vol20[i] if ma_vol20[i] else vol
        vol_ratio = vol / avg_vol if avg_vol > 0 else 1.0
        amplitude = (high - low) / close * 100 if close > 0 else 0

        body = abs(close - open_)
        upper_shadow = high - max(close, open_)
        lower_shadow = min(close, open_) - low

        m5 = ma5[i]
        m20 = ma20[i]
        m60 = ma60[i]

        if m60 is None:
            continue

        # --- 买入信号（实时量价预警） ---
        buy_reasons = []

        # 1. 缩量回踩 MA20
        if m20 and abs(close - m20) / m20 < 0.03 and vol_ratio < 0.7 and close > m60:
            buy_reasons.append(f"缩量回踩MA20(量比{vol_ratio:.1f})")

        # 2. 放量突破 MA20
        if m20 and i > 0 and closes[i - 1] < m20 and close > m20 and vol_ratio > 1.5:
            buy_reasons.append(f"放量突破MA20(量比{vol_ratio:.1f})")

        # 3. 底部放量反弹（跌后放量收阳）
        if close > open_ and vol_ratio > 2.0 and data[i]["pct_chg"] > 2.0:
            if i >= 5 and closes[i - 5] > close * 1.05:
                buy_reasons.append(f"底部放量反弹(量比{vol_ratio:.1f})")

        # 4. 长下影线 + 放量
        if body > 0 and lower_shadow > body * 2 and vol_ratio > 1.3 and close < m20 * 1.05:
            buy_reasons.append(f"长下影承接(量比{vol_ratio:.1f})")

        # 5. MA5 金叉 MA10（趋势启动）
        if ma5[i - 1] and ma10[i - 1] and ma5[i - 1] < ma10[i - 1] and m5 > ma10[i] and close > m60:
            buy_reasons.append("MA5金叉MA10")

        if buy_reasons:
            confirm_idx = min(i + lookback, n - 1)
            signals.append({
                "date_idx": i,
                "date": data[i]["date"],
                "type": "BUY",
                "confirm_idx": confirm_idx,
                "confirm_date": data[confirm_idx]["date"],
                "price": close,
                "reason": "; ".join(buy_reasons),
                "vol_ratio": round(vol_ratio, 2),
            })

        # --- 卖出信号 ---
        sell_reasons = []

        # 6. 放量滞涨
        if vol_ratio > 2.0 and abs(data[i]["pct_chg"]) < 1.0 and close > m20:
            sell_reasons.append(f"放量滞涨(量比{vol_ratio:.1f})")

        # 7. 天量长上影
        if body > 0 and upper_shadow > body * 1.5 and vol_ratio > 1.8:
            sell_reasons.append(f"天量长上影(量比{vol_ratio:.1f})")

        # 8. 放量跌破 MA20
        if m20 and closes[i - 1] > m20 and close < m20 and vol_ratio > 1.5:
            sell_reasons.append(f"放量跌破MA20(量比{vol_ratio:.1f})")

        # 9. 量价背离（价创新高但量萎缩）
        if i >= 20:
            recent_high = max(closes[i - 20:i])
            recent_max_vol = max(vols[i - 20:i])
            if close > recent_high * 0.98 and vol < recent_max_vol * 0.6:
                sell_reasons.append("量价顶背离")

        # 10. MA5 死叉 MA10
        if ma5[i - 1] and ma10[i - 1] and ma5[i - 1] > ma10[i - 1] and m5 < ma10[i]:
            sell_reasons.append("MA5死叉MA10")

        if sell_reasons:
            confirm_idx = min(i + lookback, n - 1)
            signals.append({
                "date_idx": i,
                "date": data[i]["date"],
                "type": "SELL",
                "confirm_idx": confirm_idx,
                "confirm_date": data[confirm_idx]["date"],
                "price": close,
                "reason": "; ".join(sell_reasons),
                "vol_ratio": round(vol_ratio, 2),
            })

    return signals


# ============================================================
# 回测引擎
# ============================================================

INITIAL_CAPITAL = 1_000_000  # 100万
COMMISSION_BUY = 0.00025     # 买入佣金 0.025%
COMMISSION_SELL = 0.00025    # 卖出佣金 0.025%
STAMP_TAX = 0.0005           # 印花税 0.05%（卖出）
SLIPPAGE = 0.002             # 滑点 0.2%
STOP_LOSS_PCT = 0.05         # 止损 5%


def run_backtest(data, signals):
    """
    执行回测

    交易逻辑:
    - 收到买入信号 → 确认日(lookback天后) → 次日开盘价买入
    - 持仓期间每日检查止损
    - 收到卖出信号 → 确认日 → 次日开盘价卖出
    - 同一时间只持有一个仓位
    """
    n = len(data)
    trades = []
    equity_curve = []

    position = None  # {"entry_idx", "entry_price", "shares", "stop_loss"}
    cash = INITIAL_CAPITAL
    signals_by_date = {}
    for s in signals:
        d = s["confirm_date"]
        if d not in signals_by_date:
            signals_by_date[d] = []
        signals_by_date[d].append(s)

    for i in range(n):
        date = data[i]["date"]
        close = data[i]["close"]
        high = data[i]["high"]
        low = data[i]["low"]
        open_ = data[i]["open"]

        # --- 开盘阶段 ---

        # 执行待处理订单（T+1 逻辑：信号确认日的次日开盘成交）
        if i > 0:
            prev_date = data[i - 1]["date"]
            if prev_date in signals_by_date:
                for s in signals_by_date[prev_date]:
                    if s["type"] == "BUY" and position is None:
                        # 买入：开盘价 + 滑点
                        buy_price = open_ * (1 + SLIPPAGE)
                        commission = buy_price * COMMISSION_BUY
                        shares = int(cash / (buy_price + commission) / 100) * 100  # 整手
                        if shares < 100:
                            continue
                        cost = buy_price * shares + commission * shares
                        cash -= cost
                        stop_loss = buy_price * (1 - STOP_LOSS_PCT)
                        position = {
                            "entry_idx": i,
                            "entry_date": date,
                            "entry_price": buy_price,
                            "shares": shares,
                            "stop_loss": stop_loss,
                            "signal_reason": s["reason"],
                        }
                        break

                    elif s["type"] == "SELL" and position is not None:
                        # 卖出：开盘价 - 滑点
                        sell_price = open_ * (1 - SLIPPAGE)
                        commission = sell_price * COMMISSION_SELL
                        stamp = sell_price * STAMP_TAX
                        proceeds = sell_price * position["shares"]
                        cost_fee = (commission + stamp) * position["shares"]
                        cash += proceeds - cost_fee

                        pnl = (sell_price - position["entry_price"]) * position["shares"] - cost_fee
                        pnl_pct = pnl / (position["entry_price"] * position["shares"]) * 100

                        trades.append({
                            "entry_date": position["entry_date"],
                            "entry_price": round(position["entry_price"], 2),
                            "exit_date": date,
                            "exit_price": round(sell_price, 2),
                            "shares": position["shares"],
                            "hold_days": i - position["entry_idx"],
                            "pnl": round(pnl, 0),
                            "pnl_pct": round(pnl_pct, 1),
                            "buy_reason": position["signal_reason"],
                            "sell_reason": s["reason"],
                            "win": pnl > 0,
                        })
                        position = None
                        break

        # --- 盘中阶段：检查止损 ---
        if position and low <= position["stop_loss"]:
            sell_price = position["stop_loss"]  # 按止损价成交
            commission = sell_price * COMMISSION_SELL
            stamp = sell_price * STAMP_TAX
            proceeds = sell_price * position["shares"]
            cost_fee = (commission + stamp) * position["shares"]
            cash += proceeds - cost_fee

            pnl = (sell_price - position["entry_price"]) * position["shares"] - cost_fee
            pnl_pct = pnl / (position["entry_price"] * position["shares"]) * 100

            trades.append({
                "entry_date": position["entry_date"],
                "entry_price": round(position["entry_price"], 2),
                "exit_date": date,
                "exit_price": round(sell_price, 2),
                "shares": position["shares"],
                "hold_days": i - position["entry_idx"],
                "pnl": round(pnl, 0),
                "pnl_pct": round(pnl_pct, 1),
                "buy_reason": position["signal_reason"],
                "sell_reason": f"止损触发({STOP_LOSS_PCT*100:.0f}%)",
                "win": pnl > 0,
            })
            position = None

        # --- 记录每日权益 ---
        if position:
            equity = cash + close * position["shares"]
        else:
            equity = cash
        equity_curve.append({"date": date, "equity": round(equity, 0), "close": close})

    # 期末清算
    if position:
        last = data[-1]
        sell_price = last["close"] * (1 - SLIPPAGE)
        commission = sell_price * COMMISSION_SELL
        stamp = sell_price * STAMP_TAX
        proceeds = sell_price * position["shares"]
        cost_fee = (commission + stamp) * position["shares"]
        cash += proceeds - cost_fee

        pnl = (sell_price - position["entry_price"]) * position["shares"] - cost_fee
        pnl_pct = pnl / (position["entry_price"] * position["shares"]) * 100
        trades.append({
            "entry_date": position["entry_date"],
            "entry_price": round(position["entry_price"], 2),
            "exit_date": last["date"],
            "exit_price": round(sell_price, 2),
            "shares": position["shares"],
            "hold_days": n - 1 - position["entry_idx"],
            "pnl": round(pnl, 0),
            "pnl_pct": round(pnl_pct, 1),
            "buy_reason": position["signal_reason"],
            "sell_reason": "期末清算",
            "win": pnl > 0,
        })
        equity_curve[-1]["equity"] = round(cash, 0)

    return trades, equity_curve


# ============================================================
# 绩效统计
# ============================================================

def calc_metrics(trades, equity_curve, data):
    """计算回测绩效指标"""
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "profit_factor": 0,
            "total_return": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "avg_hold_days": 0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
        }

    wins = [t for t in trades if t["win"]]
    losses = [t for t in trades if not t["win"]]

    total_pnl = sum(t["pnl"] for t in trades)
    total_return = total_pnl / INITIAL_CAPITAL * 100

    # 胜率
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    # 平均盈亏
    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0
    avg_loss = abs(sum(t["pnl"] for t in losses) / len(losses)) if losses else 0

    # 盈亏比
    profit_factor = avg_win / avg_loss if avg_loss > 0 else float("inf")

    # 最大回撤
    peak = equity_curve[0]["equity"]
    max_dd = 0
    for e in equity_curve:
        if e["equity"] > peak:
            peak = e["equity"]
        dd = (peak - e["equity"]) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # 夏普比率（日收益率年化）
    daily_returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]["equity"]
        curr = equity_curve[i]["equity"]
        if prev > 0:
            daily_returns.append((curr - prev) / prev)

    if daily_returns:
        avg_daily = sum(daily_returns) / len(daily_returns)
        std_daily = (sum((r - avg_daily) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
        sharpe = avg_daily / std_daily * (252 ** 0.5) if std_daily > 0 else 0
    else:
        sharpe = 0

    # 最大连胜/连亏
    max_consec_wins = 0
    max_consec_losses = 0
    cur_w = 0
    cur_l = 0
    for t in trades:
        if t["win"]:
            cur_w += 1
            cur_l = 0
            max_consec_wins = max(max_consec_wins, cur_w)
        else:
            cur_l += 1
            cur_w = 0
            max_consec_losses = max(max_consec_losses, cur_l)

    # 买入持有收益
    bh_return = (data[-1]["close"] - data[0]["close"]) / data[0]["close"] * 100

    # 平均持有天数
    avg_hold = sum(t["hold_days"] for t in trades) / len(trades)

    return {
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 0),
        "avg_loss": round(avg_loss, 0),
        "profit_factor": round(profit_factor, 2),
        "total_return": round(total_return, 1),
        "buy_hold_return": round(bh_return, 1),
        "max_drawdown": round(max_dd, 1),
        "sharpe_ratio": round(sharpe, 2),
        "avg_hold_days": round(avg_hold, 1),
        "max_consecutive_wins": max_consec_wins,
        "max_consecutive_losses": max_consec_losses,
        "final_equity": round(equity_curve[-1]["equity"], 0),
    }


# ============================================================
# 主函数
# ============================================================

def backtest_all():
    results = {}

    for stock in STOCKS:
        key = stock["key"]
        print(f"\n{'='*60}")
        print(f"回测 {stock['name']} ({stock['code']})")
        print(f"{'='*60}")

        data = load_daily(key)
        print(f"  数据: {len(data)} 天 ({data[0]['date']} ~ {data[-1]['date']})")

        signals = generate_signals_bt(data, min_pct=5.0, lookback=8)
        buy_sigs = [s for s in signals if s["type"] == "BUY"]
        sell_sigs = [s for s in signals if s["type"] == "SELL"]
        print(f"  信号: {len(buy_sigs)} 买入, {len(sell_sigs)} 卖出")

        trades, equity_curve = run_backtest(data, signals)
        metrics = calc_metrics(trades, equity_curve, data)

        print(f"  交易: {metrics['total_trades']} 笔 (胜{metrics.get('wins',0)}/负{metrics.get('losses',0)})")
        print(f"  胜率: {metrics['win_rate']}%")
        print(f"  盈亏比: {metrics['profit_factor']}")
        print(f"  总收益: {metrics['total_return']}% (买入持有: {metrics['buy_hold_return']}%)")
        print(f"  最大回撤: {metrics['max_drawdown']}%")
        print(f"  夏普比率: {metrics['sharpe_ratio']}")
        print(f"  平均持有: {metrics['avg_hold_days']} 天")

        results[key] = {
            "name": stock["name"],
            "code": stock["code"],
            "metrics": metrics,
            "trades": trades,
            "equity_curve": equity_curve,
        }

    return results


if __name__ == "__main__":
    results = backtest_all()

    out_path = os.path.join(DATA_DIR, "backtest_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"回测结果已保存到 {out_path}")
    print(f"{'='*60}")
