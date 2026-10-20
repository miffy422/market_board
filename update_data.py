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
    """东方财富 - 日韩（真实数据，带重试）

    说明：东方财富 push2 接口返回的 f43(最新价)/f60(昨收) 为「真实值 × 100」，
    涨跌幅由 (f43 - f60) / f60 计算。云服务器 IP（如 GitHub Actions）易被接口
    限流/瞬时断开，单次请求可能返回空、超时或被重置——这里对每个指数最多重试
    3 次并做退避，且两次请求之间留 1 秒间隔，把瞬时失败降到最低。
    （注：不要给该接口加 ut/invt/Referer 等额外参数，会触发东财连接重置。）
    """
    import time
    result = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for item in EASTMONEY_GLOBAL:
        data = None
        last_err = ""
        for attempt in range(3):
            try:
                url = (
                    "http://push2.eastmoney.com/api/qt/stock/get"
                    f"?secid={item['secid']}&fields=f43,f57,f58,f60"
                )
                resp = requests.get(url, headers=headers, timeout=10)
                payload = resp.json()
                data = payload.get("data") or {}
                if data.get("f43") and data.get("f60"):
                    break
                last_err = f"空数据(rc={payload.get('rc')})"
            except Exception as e:
                last_err = str(e)
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
        if not data or not data.get("f43") or not data.get("f60"):
            print(f"⚠️ {item['name']} 失败: {last_err}")
            continue
        raw_close = data["f43"]   # 真实价 ×100
        raw_prev = data["f60"]     # 昨收 ×100
        close = round(raw_close / 100, 2)
        change_pct = round((raw_close - raw_prev) / raw_prev * 100, 2)
        result.append({
            "market": item["market"],
            "code": item["secid"],
            "name": item["name"],
            "close": close,
            "change_pct": change_pct,
            "volume": 0,
        })
        print(f"✅ {item['name']}: {close} ({change_pct}%)")
        time.sleep(1)  # 两次请求间留间隔，规避限流
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


def run_tushare_crawler():
    """tushare 东方财富资讯爬虫"""

    # 登录
    url = "https://tushare.pro/"
    cookie="uid=2|1:0|10:1788145284|3:uid|8:NTQ3OTA1|f6d64bd9a071b7a948867f4d8d62123299f6222a4709f9d3b8bd909eb12713e7; username=2|1:0|10:1788145284|8:username|12:MTgwKioqMTA2|3b0b29c6e977540eaf922e1bad9d6d0ceb6ee8daa05f79df4703c5b861f702ec"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
        "Connection": "keep-alive",
        "Cookie": cookie,
        "Host": "tushare.pro",
        "If-None-Match": 'W/"59d60271fbbff712305f1faf07752d2691d3adb4"',
        "Priority": "u=0, i",
        "Referer": "https://tushare.pro/weborder/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
    }
    session = requests.Session()
    response = session.get(url, headers=headers)
    if response.status_code==200:
        print("登录成功")
    else:
        print("登录失败")
        print(response.text)


    # 请求资讯（东方财富）
    url = "https://tushare.pro/news/eastmoney"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Host": "tushare.pro",
        "If-None-Match": 'W/"b825c874f94b4d4f8faba4c7ff9ec34cfb3a184f"',
        "Priority": "u=0, i",
        "Referer": "https://tushare.pro/news/sina",
        "Sec-Fetch-Dest": "document",
        "Cookie": cookie,
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }
    response = session.get(url, headers=headers)
    print(response.status_code)

    with open("东方财富.txt", "w", encoding="utf-8") as f:
        f.write(response.text)

    return response.text


def parse_tushare_news(html, limit=100):
    """
    解析 tushare 东方财富资讯 HTML。
    条目结构：
      <div class="none_class news_item">
          <div class="news_datetime">13:46</div>
          <div class="news_content">【标题】正文...</div>
      </div>
    """
    today = datetime.now().strftime("%Y-%m-%d")
    items = re.findall(
        r'<div class="news_datetime">(\d{2}:\d{2})</div>\s*'
        r'<div class="news_content">(.*?)</div>',
        html, re.S,
    )

    news = []
    seen = set()
    for time_str, raw in items:
        text = html_lib.unescape(re.sub(r"\s+", " ", raw)).strip()
        if not text or text in seen:
            continue
        seen.add(text)

        # 有【标题】则拆开，否则整条作为标题
        m = re.match(r"【(.+?)】(.*)", text)
        if m:
            title, content = m.group(1).strip(), m.group(2).strip()
        else:
            title, content = text, ""

        # 市场归属
        if any(k in text for k in ["港股", "恒生", "港交所", "香港"]):
            market = "HK"
        elif any(k in text for k in ["日经", "日本", "日银", "日元"]):
            market = "Japan"
        elif any(k in text for k in ["韩国", "KOSPI", "韩股", "首尔"]):
            market = "Korea"
        else:
            market = "China"

        # # 重要级别
        if any(k in text for k in ["央行", "加息", "降息", "暴跌", "大跌",
                                   "涨停", "战争", "冲突", "制裁", "危机"]):
            level = 1
        elif text.startswith("【"):
            level = 2
        else:
            level = 3

        news.append({
            "trade_date": today,
            "time": time_str,
            "source": "东方财富",
            "title": title[:120],
            "content": content[:500],
            "market":market,
            "level":level
        })
        if len(news) >= limit:
            break

    print(f"✅ 解析资讯：{len(news)} 条")
    return news


def get_news():
    """抓取 tushare 东方财富资讯并解析入库"""
    try:
        html = run_tushare_crawler()
        return parse_tushare_news(html)
    except Exception as e:
        print(f"❌ 获取 tushare 资讯失败: {e}")
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
