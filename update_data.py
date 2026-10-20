"""
数据抓取脚本 - 生成 SQLite 数据库
每天运行一次，保留历史数据，只替换当日
"""

import os
import re
import json
import html as html_lib
import sqlite3
import requests
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

# CNBC 全球指数（日韩）—— 东方财富 push2 在 GitHub Actions 云服务器 IP 上常被挡，
# 故日韩行情改用 CNBC 公开行情接口（对数据中心 IP 友好，返回干净 JSON）。
CNBC_GLOBAL = [
    {"symbol": ".N225", "name": "日经225", "market": "Japan"},
    {"symbol": ".KS11", "name": "韩国综合指数", "market": "Korea"},
    {"symbol": ".DJI", "name": "道琼斯指数", "market": "US"},
    {"symbol": ".IXIC", "name": "纳斯达克指数", "market": "US"},
    {"symbol": ".INX", "name": "标普500", "market": "US"},
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
    """CNBC 行情接口 - 日韩（真实数据，带重试）

    说明：原东方财富 push2 接口在 GitHub Actions 的云服务器 IP 上经常被挡
    （返回空/非 JSON，导致 json 解析失败），因此日韩行情改用 CNBC 公开行情接口，
    它对数据中心 IP 友好。CNBC 返回 JSON，关键字段：
        last                 最新价（带千分位逗号，如 "64,075.42"）
        change_pct          涨跌幅（带百分号，如 "-1.30%"）
        previous_day_closing 昨收
    每个指数最多重试 3 次并做退避，两次请求之间留 1 秒间隔。
    """
    import time
    result = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Referer": "https://www.cnbc.com/",
    }
    for item in CNBC_GLOBAL:
        data = None
        last_err = ""
        for attempt in range(3):
            try:
                url = (
                    "https://quote.cnbc.com/quote-html-webservice/restQuote/"
                    "symbolType/symbol"
                    f"?symbols={item['symbol']}&requestMethod=itv&noform=1"
                    "&partnerId=2&fund=1&exthrs=1&output=json"
                )
                resp = requests.get(url, headers=headers, timeout=10)
                payload = resp.json()
                quotes = payload.get("FormattedQuoteResult", {}).get(
                    "FormattedQuote", []
                )
                if quotes:
                    data = quotes[0]
                    break
                last_err = "空数据"
            except Exception as e:
                last_err = str(e)
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
        if not data:
            print(f"⚠️ {item['name']} 失败: {last_err}")
            continue
        try:
            close = float(str(data.get("last", "0")).replace(",", ""))
            change_pct = float(str(data.get("change_pct", "0")).replace("%", ""))
        except (ValueError, TypeError):
            print(f"⚠️ {item['name']} 字段解析失败: {data}")
            continue
        result.append({
            "market": item["market"],
            "code": item["symbol"],
            "name": item["name"],
            "close": close,
            "change_pct": change_pct,
            "volume": 0,
        })
        print(f"✅ {item['name']}: {close} ({change_pct}%)")
        time.sleep(1)  # 两次请求间留间隔
    return result


def get_mock_indices():
    """日韩备用数据（仅当接口全部异常时回退）"""
    print("⚠️ 日韩接口异常，使用模拟数据")
    return [
        {"market": "Japan", "code": "N225", "name": "日经225",
         "close": 38500.0, "change_pct": 0.5, "volume": 0},
        {"market": "Korea", "code": "KS11", "name": "韩国综合指数",
         "close": 2750.0, "change_pct": -0.3, "volume": 0},
    ]


def _classify_market(text):
    """根据新闻文本判断所属市场"""
    if any(k in text for k in ["港股", "恒生", "港交所", "香港"]):
        return "HK"
    if any(k in text for k in ["日经", "日本", "日银", "日元", "东证"]):
        return "Japan"
    if any(k in text for k in ["韩国", "KOSPI", "韩股", "首尔", "韩元"]):
        return "Korea"
    if any(k in text for k in ["美股", "美国", "美联储", "纳斯达克", "道琼斯",
                               "标普", "中概股", "中概", "华尔街", "欧央行",
                               "欧洲央行", "欧洲", "地缘", "关税", "特朗普"]):
        return "US"
    return "China"


def _classify_level(text):
    """根据关键词判断重要级别"""
    if any(k in text for k in ["央行", "加息", "降息", "暴跌", "大跌",
                               "涨停", "战争", "冲突", "制裁", "危机"]):
        return 1
    if text.startswith("【"):
        return 2
    return 3


def fetch_eastmoney_news():
    """东方财富 7×24 快讯（公开接口，无需登录）

    原 tushare.pro 爬虫依赖一个写死的浏览器 session cookie，cookie 过期后
    服务器返回登录页空壳、抓不到任何新闻（现象：run_tushare_crawler 返回 200
    但正文是 SPA 空壳，parse 后 0 条）。这里改为直接调用东方财富官方公开快讯
    接口（即 tushare 原来抓取的同一数据源），无需任何鉴权，返回结构化 JSON。
    接口返回形如 `var ajaxResult={...}`，需先去掉前缀再解析；新闻列表在
    LivesList 字段，单条含 title(标题) / digest(摘要) / showtime(发布时间)。
    """
    import time

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Referer": "https://kuaixun.eastmoney.com/",
    }
    # zhiboall=全部实时快讯(70条)；102=全球股市快讯(兜底)
    endpoints = [
        "https://newsapi.eastmoney.com/kuaixun/v1/getlist_zhiboall_ajaxResult_70_1_.html",
        "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html",
    ]
    today = datetime.now().strftime("%Y-%m-%d")
    last_err = ""
    for url in endpoints:
        for attempt in range(3):
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                text = resp.text
                if not text.startswith("var ajaxResult="):
                    raise ValueError("返回格式异常(可能被拦截)")
                payload = json.loads(text[len("var ajaxResult="):].strip())
                lives = payload.get("LivesList") or []
                if not lives:
                    raise ValueError("LivesList 为空")
                news = []
                seen = set()
                for it in lives:
                    title = (it.get("title") or it.get("simtitle") or "").strip()
                    digest = (it.get("digest") or it.get("simdigest") or "").strip()
                    if not title:
                        continue
                    key = title + "|" + digest
                    if key in seen:
                        continue
                    seen.add(key)
                    showtime = it.get("showtime") or it.get("ordertime") or ""
                    m = re.search(r"(\d{2}:\d{2})", showtime)
                    t = m.group(1) if m else ""
                    full = f"{title} {digest}"
                    news.append({
                        "trade_date": today,
                        "time": t,
                        "source": "东方财富",
                        "title": title[:120],
                        "content": digest[:500],
                        "market": _classify_market(full),
                        "level": _classify_level(full),
                    })
                print(f"✅ 东方财富快讯：{len(news)} 条")
                return news
            except Exception as e:
                last_err = str(e)
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    print(f"⚠️ 东方财富快讯获取失败: {last_err}")
    return []


def get_news():
    """获取新闻资讯（东方财富 7×24 快讯）"""
    try:
        return fetch_eastmoney_news()
    except Exception as e:
        print(f"❌ 获取新闻资讯失败: {e}")
        return []


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
            today, item["market"], item["code"], item["name"],
            item["close"], item["change_pct"], item.get("volume", 0), now,
        ))

    for item in news_list:
        c.execute("""
            INSERT INTO news (trade_date, time, source, title, content, market, level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            item["trade_date"], item["time"], item["source"],
            item["title"], item["content"], item["market"], item["level"],
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

    save_to_db(indices, news)
    print("完成")
