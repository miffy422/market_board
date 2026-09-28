"""
数据抓取脚本 - 生成 SQLite 数据库
每天运行一次，保留历史数据，只替换当日
"""
import os
import re
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



def _tushare_session():
    """创建带 Cookie 的 tushare 会话；Cookie 从环境变量读取，不要硬编码。"""
    cookie = os.environ.get("TUSHARE_COOKIE", "").strip()
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    if cookie:
        session.headers.update({"Cookie": cookie})
    else:
        print("⚠️ 未设置 TUSHARE_COOKIE，tushare 网页资讯可能无法登录/返回空结果")
    return session


def _clean_text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _infer_market_level(title):
    t = title
    market = "China"
    if any(k in t for k in ["港股", "香港", "港交所", "恒生"]):
        market = "HK"
    elif any(k in t for k in ["日本", "日经", "日银", "日本央行"]):
        market = "Japan"
    elif any(k in t for k in ["韩国", "韩股", "首尔", "KOSPI"]):
        market = "Korea"

    level = 3
    if any(k in t for k in ["央行", "加息", "降息", "通胀", "风险", "大跌", "危机", "监管", "证监会"]):
        level = 1
    elif any(k in t for k in ["政策", "改革", "数据", "发布", "净买入", "南向资金"]):
        level = 2
    return market, level


def _parse_tushare_news_html(html, limit=50):
    """从 tushare 资讯 HTML 中保守提取标题链接；解析不到时返回空列表。"""
    items, seen = [], set()

    # 优先 BeautifulSoup，失败则退化到正则；requirements 需安装 beautifulsoup4
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        anchors = soup.find_all("a")
        candidates = []
        for a in anchors:
            title = _clean_text(a.get_text(" "))
            href = a.get("href", "") or ""
            if not title or len(title) < 8 or len(title) > 120:
                continue
            if any(x in href for x in ["/login", "/register", "/weborder", "javascript:"]):
                continue
            candidates.append((title, href))
    except Exception:
        candidates = []
        for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.S|re.I):
            href, title = m.group(1), _clean_text(m.group(2))
            if not title or len(title) < 8 or len(title) > 120:
                continue
            if any(x in href for x in ["/login", "/register", "/weborder", "javascript:"]):
                continue
            candidates.append((title, href))

    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M")
    for title, href in candidates:
        key = (title, href)
        if key in seen:
            continue
        seen.add(key)
        market, level = _infer_market_level(title)
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


def fetch_tushare_news(limit=50):
    """按你给定的思路抓取 tushare 网页的东方财富资讯，并解析为展板 news 结构。"""
    home = "https://tushare.pro/"
    news_url = "https://tushare.pro/news/eastmoney"
    session = _tushare_session()

    # 先访问首页建立会话/登录态，再访问资讯页
    r0 = session.get(home, timeout=20)
    if r0.status_code != 200:
        print(f"❌ tushare 首页登录态请求失败: HTTP {r0.status_code}")
        return []

    headers = {"Referer": home, "Accept": session.headers.get("Accept", "*/*")}
    r = session.get(news_url, headers=headers, timeout=20)
    if r.status_code != 200:
        print(f"❌ tushare 东方财富资讯请求失败: HTTP {r.status_code}")
        return []

    # 保存原始页便于排查结构变化；不要提交到仓库
    Path("tushare_eastmoney.html").write_text(r.text, encoding="utf-8")
    news = _parse_tushare_news_html(r.text, limit=limit)
    print(f"✅ tushare 资讯解析：{len(news)} 条（原始页已保存到 tushare_eastmoney.html）")
    return news


def get_news():
    """兼容入口：优先使用 tushare 网页爬虫；失败时不造演示数据，返回空列表。"""
    try:
        news = fetch_tushare_news()
        if news:
            return news
        print("⚠️ tushare 资讯未解析到条目，今日 news 将为空；请检查 TUSHARE_COOKIE 或页面结构")
        return []
    except Exception as e:
        print(f"❌ 获取 tushare 资讯失败: {e}")
        return []


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

