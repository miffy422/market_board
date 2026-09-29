"""
数据抓取脚本 - 生成 SQLite 数据库
每天运行一次，保留历史数据，只替换当日
"""

import os
import re
import html as html_lib
import sqlite3
import requests
from datetime import datetime
from pathlib import Path

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
    c.execute("""
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
    """)
    c.execute("""
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
    """)
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
                "market": market,
                "code": code,
                "name": name,
                "close": close,
                "change_pct": change_pct,
                "volume": 0,
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
                "http://push2.eastmoney.com/api/qt/stock/get"
                f"?secid={item['secid']}&fields=f43,f44,f57,f58,f60"
            )
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json().get("data", {}) or {}
            close = data.get("f43", 0) or 0
            change_pct = data.get("f58", 0) or 0
            if close > 10000:
                close = close / 100
            result.append({
                "market": item["market"],
                "code": item["secid"],
                "name": item["name"],
                "close": round(close, 2),
                "change_pct": round(change_pct, 2),
                "volume": 0,
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


def normalize_cookie(raw):
    """
    把 Secret 里可能带有的换行/缩进规整成单行 Cookie。
    不打印原文。
    """
    pairs = []
    for line in re.split(r"[\r\n]+", raw or ""):
        for part in line.split(";"):
            part = part.strip()
            if part:
                pairs.append(part)
    return "; ".join(pairs)


def clean_text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html_lib.unescape(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def infer_market_level(title):
    if any(k in title for k in ["港股", "香港", "港交所", "恒生"]):
        market = "HK"
    elif any(k in title for k in ["日本", "日经", "日银", "日本央行"]):
        market = "Japan"
    elif any(k in title for k in ["韩国", "韩股", "首尔", "KOSPI"]):
        market = "Korea"
    else:
        market = "China"

    level = 3
    if any(k in title for k in ["央行", "加息", "降息", "通胀", "风险", "大跌", "危机", "监管", "证监会"]):
        level = 1
    elif any(k in title for k in ["政策", "改革", "数据", "发布", "净买入", "南向资金"]):
        level = 2
    return market, level


def parse_news_loose(html, limit=80):
    """
    宽松解析：只提取 <a> 文本/href。
    不追求完美，优先保证不因为选择器太严格而 0 条。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M")
    items = []
    seen = set()

    bad_href = ["/login", "/register", "/weborder", "javascript:", "logout", "settings"]
    for m in re.finditer(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        html,
        flags=re.I | re.S,
    ):
        href = (m.group(1) or "").strip()
        title = clean_text(m.group(2))
        if not title or len(title) < 4:
            continue
        if any(b in href.lower() for b in bad_href):
            continue

        key = (title, href)
        if key in seen:
            continue
        seen.add(key)

        market, level = infer_market_level(title)
        items.append({
            "trade_date": today,
            "time": now,
            "source": "Tushare/东方财富",
            "title": title,
            "content": href,
            "market": market,
            "level": level,
        })
        if len(items) >= limit:
            break
    return items


def fetch_tushare_news():
    """
    按你本地可运行的最小思路抓 tushare 东方财富资讯：
    直接 GET /news/eastmoney，保存 东方财富.txt，再宽松解析入库。
    """
    cookie = normalize_cookie(os.environ.get("TUSHARE_COOKIE", ""))
    if not cookie:
        print("⚠️ 未设置 TUSHARE_COOKIE，跳过 tushare 资讯")

    url = "https://tushare.pro/news/eastmoney"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Connection": "keep-alive",
        "Cookie": cookie,
        "Host": "tushare.pro",
        "Referer": "https://tushare.pro/news/sina",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        print(f"tushare status={resp.status_code} len={len(resp.text)} final_url={resp.url}")
        resp.raise_for_status()

        # 和你本地脚本保持一致，先落盘方便肉眼看
        Path("东方财富.txt").write_text(resp.text, encoding="utf-8")
        # 另存一份调试名，方便 Actions artifact 上传排查
        Path("tushare_eastmoney.html").write_text(resp.text, encoding="utf-8")

        news = parse_news_loose(resp.text, limit=80)
        print(f"✅ tushare 宽松解析：{len(news)} 条；原始 HTML 已保存到 东方财富.txt / tushare_eastmoney.html")
        return news
    except Exception as e:
        print(f"❌ 获取 tushare 资讯失败: {e}")
        return []


def get_news():
    """
    资讯入口：不造演示数据。
    抓不到/解析不到就返回空列表，避免展板混入假新闻。
    """
    return fetch_tushare_news()


def save_to_db(indices, news_list):
    """写入数据库：保留历史，只替换当日"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M:%S")

    c.execute("DELETE FROM indices WHERE trade_date = ?", (today,))
    c.execute("DELETE FROM news WHERE trade_date = ?", (today,))

    for item in indices:
        c.execute("""
            INSERT INTO indices (trade_date, market, code, name, close, change_pct, volume, update_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            today,
            item["market"],
            item["code"],
            item["name"],
            item["close"],
            item["change_pct"],
            item.get("volume", 0),
            now,
        ))

    for item in news_list:
        c.execute("""
            INSERT INTO news (trade_date, time, source, title, content, market, level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            item["trade_date"],
            item["time"],
            item["source"],
            item["title"],
            item["content"],
            item["market"],
            item["level"],
        ))

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
    if not news:
        print("⚠️ 今日 news 为空：请查看 东方财富.txt 的 status/len，或检查 TUSHARE_COOKIE 权限")

    save_to_db(indices, news)
    print("完成")
