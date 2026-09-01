"""
数据抓取脚本 - 生成 SQLite 数据库
每天运行一次，保留历史数据，只替换当日
"""
import sqlite3
import requests
import re
from datetime import datetime

DB_PATH = "market.db"

# 腾讯财经接口（A股+港股）
TENCENT_CODES = {
    "sh000001": ("上证指数", "China"),
    "sz399001": ("深证成指", "China"),
    "sz399006": ("创业板指", "China"),
    "sh000300": ("沪深300", "China"),
    "hkHSI":    ("恒生指数", "HK"),
    "hkHSTECH": ("恒生科技指数", "HK"),
}

# 东方财富全球指数（日韩）
EASTMONEY_GLOBAL = [
    {"secid": "100.N225", "name": "日经225", "market": "Japan"},
    {"secid": "100.KS11", "name": "韩国综合指数", "market": "Korea"},
]


def init_db():
    """初始化数据库表（如果不存在）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS indices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT,
            market TEXT,
            code TEXT,
            name TEXT,
            close REAL,
            change_pct REAL,
            volume REAL,
            update_time TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT,
            time TEXT,
            source TEXT,
            title TEXT,
            content TEXT,
            market TEXT,
            level INTEGER
        )
    ''')
    conn.commit()
    conn.close()


def fetch_tencent():
    """腾讯财经 - A股+港股"""
    codes = ",".join(TENCENT_CODES.keys())
    url = f"http://qt.gtimg.cn/q={codes}"
    try:
        resp = requests.get(url, timeout=15)
        resp.encoding = "gbk"
        result = []
        for line in resp.text.split(";"):
            match = re.search(r'v_(\w+)="([^"]+)"', line)
            if not match:
                continue
            code, raw = match.groups()
            parts = raw.split("~")
            if len(parts) < 6:
                continue
            name, close_str, prev_str = parts[1], parts[3], parts[4]
            try:
                close = float(close_str)
                prev = float(prev_str)
                change_pct = round((close - prev) / prev * 100, 2) if prev else 0
            except ValueError:
                continue
            _, market = TENCENT_CODES.get(code, (name, "Unknown"))
            result.append({
                "market": market, "code": code, "name": name,
                "close": close, "change_pct": change_pct, "volume": 0
            })
        print(f"✅ 腾讯接口：{len(result)} 条")
        return result
    except Exception as e:
        print(f"❌ 腾讯接口失败: {e}")
        return []


def fetch_global():
    """东方财富 - 日韩"""
    result = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for item in EASTMONEY_GLOBAL:
        try:
            url = (
                f"http://push2.eastmoney.com/api/qt/stock/get"
                f"?secid={item['secid']}&fields=f43,f44,f57,f58,f60"
            )
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json().get("data", {})
            close = data.get("f43", 0)
            change_pct = data.get("f58", 0)
            if close > 10000:
                close = close / 100
            result.append({
                "market": item["market"], "code": item["secid"], "name": item["name"],
                "close": round(close, 2), "change_pct": round(change_pct, 2), "volume": 0
            })
            print(f"✅ {item['name']}: {close} ({change_pct}%)")
        except Exception as e:
            print(f"⚠️ {item['name']} 失败: {e}")
    return result


def get_mock_indices():
    """日韩备用数据"""
    print("⚠️ 日韩使用模拟数据")
    return [
        {"market": "Japan", "code": "N225", "name": "日经225",
         "close": 38500.0, "change_pct": 0.5, "volume": 0},
        {"market": "Korea", "code": "KS11", "name": "韩国综合指数",
         "close": 2750.0, "change_pct": -0.3, "volume": 0},
    ]


def get_news():
    """新闻（后续可替换为 RSS/API）"""
    today = datetime.now().strftime("%Y-%m-%d")
    return [
        {"trade_date": today, "time": "09:15", "source": "央行",
         "title": "今日公开市场开展1000亿元7天期逆回购操作",
         "content": "维护银行体系流动性合理充裕", "market": "China", "level": 1},
        {"trade_date": today, "time": "11:30", "source": "证监会",
         "title": "就《上市公司监管指引》公开征求意见",
         "content": "进一步规范上市公司信息披露行为", "market": "China", "level": 2},
        {"trade_date": today, "time": "14:00", "source": "日经新闻",
         "title": "日本央行行长暗示年内可能调整宽松政策",
         "content": "关注通胀持续性和工资增长", "market": "Japan", "level": 1},
        {"trade_date": today, "time": "15:30", "source": "港交所",
         "title": "港股通今日净买入45亿港元",
         "content": "科技股获持续加仓", "market": "HK", "level": 2},
    ]


def save_to_db(indices, news_list):
    """写入数据库：保留历史，只替换当日"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M:%S")

    # 删除当日旧数据（避免重复），保留其他日期历史
    c.execute("DELETE FROM indices WHERE trade_date = ?", (today,))
    c.execute("DELETE FROM news WHERE trade_date = ?", (today,))

    for item in indices:
        c.execute('''
            INSERT INTO indices (trade_date, market, code, name, close, change_pct, volume, update_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (today, item["market"], item["code"], item["name"],
              item["close"], item["change_pct"], item.get("volume", 0), now))

    for item in news_list:
        c.execute('''
            INSERT INTO news (trade_date, time, source, title, content, market, level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (item["trade_date"], item["time"], item["source"], item["title"],
              item["content"], item["market"], item["level"]))

    conn.commit()
    conn.close()
    print(f"✅ 已保存 {today}：指数 {len(indices)} 条，新闻 {len(news_list)} 条")


if __name__ == "__main__":
    init_db()
    print(f"开始抓取数据... {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    indices = fetch_tencent()
    global_idx = fetch_global()

    if global_idx:
        indices += global_idx
    else:
        indices += get_mock_indices()

    news = get_news()
    save_to_db(indices, news)
    print("完成")
