"""
RTZigzag 看板数据注入脚本
将分析结果注入HTML模板
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "rt_zigzag_template.html")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "rt_zigzag_dashboard.html")

# 股票配置
STOCKS = [
    {"key": "smic",       "code": "688981", "name": "中芯国际"},
    {"key": "gigadevice", "code": "603986", "name": "兆易创新"},
    {"key": "goldwind",   "code": "002202", "name": "金风科技"},
    {"key": "bright",     "code": "688333", "name": "铂力特"},
    {"key": "leader",     "code": "688017", "name": "绿的谐波"},
    {"key": "siruixin",   "code": "688102", "name": "斯瑞新材"},
    {"key": "montage",    "code": "688008", "name": "澜起科技"},
]

# 加载数据
raw_data = {}
extrema_data = {}
alerts_data = {}
signals_data = {}

for stock in STOCKS:
    key = stock["key"]

    # 30分钟K线
    min_path = os.path.join(DATA_DIR, f"{key}_30min.json")
    if os.path.exists(min_path):
        with open(min_path) as f:
            raw_data[key] = json.load(f)

# 加载分析结果
results_path = os.path.join(DATA_DIR, "rt_zigzag_results.json")
if os.path.exists(results_path):
    with open(results_path) as f:
        results = json.load(f)

    for key, result in results.items():
        extrema_data[key] = {
            "peaks": result.get("peaks", []),
            "troughs": result.get("troughs", []),
        }
        alerts_data[key] = result.get("alerts", [])
        signals_data[key] = result.get("signals", [])

# 加载模板
with open(TEMPLATE_PATH, encoding="utf-8") as f:
    template = f.read()

# 注入数据
template = template.replace("__RAW_30MIN__", json.dumps(raw_data, ensure_ascii=False))
template = template.replace("__EXTREMA__", json.dumps(extrema_data, ensure_ascii=False))
template = template.replace("__ALERTS__", json.dumps(alerts_data, ensure_ascii=False))
template = template.replace("__SIGNALS__", json.dumps(signals_data, ensure_ascii=False))

# 保存
os.makedirs(OUTPUT_DIR, exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write(template)

print(f"✅ 看板已生成: {OUTPUT_PATH}")
print(f"   股票数量: {len(raw_data)}")
for key in raw_data:
    bars = len(raw_data[key])
    sigs = len(signals_data.get(key, []))
    high_sig = len([s for s in signals_data.get(key, []) if s.get("confidence", 0) >= 3])
    print(f"   {key}: {bars}根30min K线, {sigs}个共振信号({high_sig}个高置信)")
