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

# CNBC 大宗商品（黄金/白银/原油/铜/大豆）—— 与日韩/美股共用同一 CNBC 通道。
# 东方财富 push2 对云服务器 IP 常被挡，故海外品种统一走 CNBC。
# 期货连续合约符号（@X.1）：GC=黄金 SI=白银 CL=WTI原油 HG=铜 S=大豆
CNBC_COMMODITIES = [
    {"symbol": "@GC.1", "name": "黄金", "market": "Commodity"},
    {"symbol": "@SI.1", "name": "白银", "market": "Commodity"},
    {"symbol": "@CL.1", "name": "WTI原油", "market": "Commodity"},
    {"symbol": "@HG.1", "name": "铜", "market": "Commodity"},
    {"symbol": "@S.1", "name": "大豆", "market": "Commodity"},
]

# ============ 国债收益率曲线（中/美）============
# 东方财富数据中心「中美国债收益率」报表（data.eastmoney.com/cjsj/zmgzsyl.html 的后台接口），
# 一次请求同时返回中国（中债）与美国（美联储）的 2Y/5Y/10Y/30Y 收益率，字段含义已用
# 美国财政部官方 CSV 交叉验证：
#   EMM00588704 中国2年  EMM00166462 中国5年  EMM00166466 中国10年  EMM00166469 中国30年
#   EMG00001306 美国2年  EMG00001308 美国5年  EMG00001310 美国10年  EMG00001312 美国30年
# 注：与 push2（行情接口）不同，datacenter-web 实测对云服务器 IP 友好、5/5 稳定。
YIELD_REPORT_API = (
    "https://datacenter-web.eastmoney.com/api/data/v1/get"
    "?reportName=RPTA_WEB_TREASURYYIELD&columns=ALL&pageSize=10"
    "&sortColumns=SOLAR_DATE&sortTypes=-1&source=WEB&client=WEB"
)

YIELD_FIELDS = {
    "CN": {
        "2Y": "EMM00588704",
        "5Y": "EMM00166462",
        "10Y": "EMM00166466",
        "30Y": "EMM00166469",
    },
    "US": {
        "2Y": "EMG00001306",
        "5Y": "EMG00001308",
        "10Y": "EMG00001310",
        "30Y": "EMG00001312",
    },
}

YIELD_TENORS = ["2Y", "5Y", "10Y", "30Y"]


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
    # 国债收益率（region=CN/US，tenor=2Y/5Y/10Y/30Y；chg_bp 为较前一交易日的变动，单位 bp）
    c.execute("""
        CREATE TABLE IF NOT EXISTS yields (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT,
            region TEXT,
            tenor TEXT,
            yield_val REAL,
            prev_val REAL,
            chg_bp REAL,
            update_time TEXT
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


def _fetch_cnbc(items):
    """通用 CNBC 行情抓取（日韩/美股/大宗商品共用，带重试）

    说明：原东方财富 push2 接口在 GitHub Actions 的云服务器 IP 上经常被挡
    （返回空/非 JSON，导致 json 解析失败），因此这些海外品种统一改用 CNBC
    公开行情接口，它对数据中心 IP 友好，返回干净 JSON。关键字段：
        last          最新价（带千分位逗号，如 "64,075.42"）
        change_pct   涨跌幅（带百分号，如 "-1.30%"）
    每个品种最多重试 3 次并做退避，两次请求之间留 1 秒间隔。
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
    for item in items:
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


def fetch_global():
    """CNBC 行情接口 - 日韩 + 美股"""
    return _fetch_cnbc(CNBC_GLOBAL)


def fetch_commodities():
    """CNBC 行情接口 - 大宗商品（黄金/白银/WTI原油/铜/大豆）"""
    return _fetch_cnbc(CNBC_COMMODITIES)


def _fetch_treasury_csv_us():
    """备用源：美国财政部官方日度收益率 CSV（仅美国）"""
    import csv
    import io
    year = datetime.now().year
    url = (
        "https://home.treasury.gov/resource-center/data-chart-center/"
        f"interest-rates/daily-treasury-rates.csv/{year}/all"
        f"?type=daily_treasury_yield_curve&field_tdr_date_value={year}"
        "&page&_format=csv"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    if not rows:
        raise ValueError("CSV 无数据")
    # CSV 行不保证有序，按日期排序后取最近两行
    def _key(r):
        return datetime.strptime(r["Date"], "%m/%d/%Y")
    rows.sort(key=_key, reverse=True)
    latest, prev = rows[0], rows[1] if len(rows) > 1 else rows[0]
    out = {}
    for tenor, col in [("2Y", "2 Yr"), ("5Y", "5 Yr"), ("10Y", "10 Yr"), ("30Y", "30 Yr")]:
        try:
            out[tenor] = (float(latest[col]), float(prev[col]))
        except (KeyError, ValueError, TypeError):
            continue
    if not out:
        raise ValueError("CSV 字段解析失败")
    return out


def fetch_yields():
    """中美国债收益率（2Y/5Y/10Y/30Y），含较前一交易日变动

    主源：东方财富数据中心 RPTA_WEB_TREASURYYIELD（一次拿全中美两国）。
    备源：美国财政部官方 CSV（仅美国；中国缺失时保留主源或跳过）。
    返回：{"CN": {"2Y": (最新, 前值), ...}, "US": {...}}
    """
    import time
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Referer": "https://data.eastmoney.com/",
    }
    result = {}
    last_err = ""
    for attempt in range(3):
        try:
            resp = requests.get(YIELD_REPORT_API, headers=headers, timeout=15)
            payload = resp.json()
            data = (payload.get("result") or {}).get("data") or []
            if not data:
                raise ValueError("返回为空(可能被拦截)")
            # data 已按 SOLAR_DATE 倒序，取最近两行算日变动
            latest = data[0]
            prev = data[1] if len(data) > 1 else data[0]
            for region, fields in YIELD_FIELDS.items():
                vals = {}
                for tenor in YIELD_TENORS:
                    col = fields[tenor]
                    cur_v, prev_v = latest.get(col), prev.get(col)
                    if cur_v is None or prev_v is None:
                        continue
                    vals[tenor] = (float(cur_v), float(prev_v))
                if vals:
                    result[region] = vals
            if result:
                break
            last_err = "字段全为空"
        except Exception as e:
            last_err = str(e)
        if attempt < 2:
            time.sleep(0.5 * (attempt + 1))

    if not result:
        print(f"⚠️ 国债收益率主源失败: {last_err}")

    # 主源缺美国 → 用财政部官方 CSV 补
    if "US" not in result:
        try:
            result["US"] = _fetch_treasury_csv_us()
            print("ℹ️ 美国收益率已由财政部 CSV 补齐")
        except Exception as e:
            print(f"⚠️ 美国收益率备用源也失败: {e}")

    for region, vals in result.items():
        label = "中国" if region == "CN" else "美国"
        desc = " ".join(
            f"{t}={vals[t][0]:.2f}" for t in YIELD_TENORS if t in vals
        )
        if "2Y" in vals and "10Y" in vals:
            spread = (vals["10Y"][0] - vals["2Y"][0]) * 100
            desc += f" | 10Y-2Y={spread:+.0f}bp"
        print(f"✅ {label}国债收益率: {desc}")
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


def yields_to_index_rows(yields):
    """把中美 10Y 收益率与 10Y-2Y 利差转成 indices 行，供看板统一展示/预警。

    收益率以"点位"写入 close，change_pct 记录较前值的变动百分比（保留两位，
    便于复用既有的涨跌配色与异动预警逻辑）。
    """
    rows = []
    for region, vals in yields.items():
        market = "BondCN" if region == "CN" else "BondUS"
        label = "中国" if region == "CN" else "美国"
        if "2Y" in vals and "10Y" in vals:
            cn2, cn2p = vals["2Y"]
            cn10, cn10p = vals["10Y"]
            cur_spread_bp = (cn10 - cn2) * 100
            prev_spread_bp = (cn10p - cn2p) * 100
            # 利差以 bp 为单位，涨跌用 bp 的绝对变化表达更直观，这里换算成百分比
            chg_pct = (
                round((cur_spread_bp - prev_spread_bp) / abs(prev_spread_bp) * 100, 2)
                if prev_spread_bp else 0.0
            )
            rows.append({
                "market": market,
                "code": f"{region}2S10S",
                "name": f"{label} 10Y-2Y利差",
                "close": round(cur_spread_bp, 0),
                "change_pct": chg_pct,
                "volume": 0,
            })
    return rows


def save_yields(yields, conn):
    """把收益率写入 yields 表（当日的先删后插）"""
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M:%S")
    conn.execute("DELETE FROM yields WHERE trade_date = ?", (today,))
    n = 0
    for region, vals in yields.items():
        for tenor, (cur_v, prev_v) in vals.items():
            conn.execute("""
                INSERT INTO yields (trade_date, region, tenor, yield_val, prev_val, chg_bp, update_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                today, region, tenor, round(cur_v, 4), round(prev_v, 4),
                round((cur_v - prev_v) * 100, 2), now,
            ))
            n += 1
    return n


def _classify_market(text):
    """根据新闻文本判断所属市场"""
    if any(k in text for k in ["港股", "恒生", "港交所", "香港"]):
        return "HK"
    if any(k in text for k in ["日经", "日本", "日银", "日元", "东证"]):
        return "Japan"
    if any(k in text for k in ["韩国", "KOSPI", "韩股", "首尔", "韩元"]):
        return "Korea"
    if any(k in text for k in ["黄金", "白银", "原油", "油价", "铜", "镍", "锂",
                               "大豆", "天然气", "有色金属", "大宗商品", "OPEC",
                               "减产", "矿石", "煤炭", "钢铁"]):
        return "Commodity"
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


def save_to_db(indices, news_list, yields=None):
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

    # 收益率明细写入 yields 表（利差等指数行已由调用方并入 indices）
    y_count = save_yields(yields, conn) if yields else 0

    conn.commit()
    conn.close()
    print(
        f"✅ 已保存 {today}：指数 {len(indices)} 条，"
        f"新闻 {len(news_list)} 条，收益率 {y_count} 条"
    )


if __name__ == "__main__":
    init_db()
    print(f"开始抓取数据... {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    indices = fetch_tencent()
    global_idx = fetch_global()
    if global_idx:
        indices += global_idx
    else:
        indices += get_mock_indices()

    indices += fetch_commodities()

    yields = fetch_yields()
    indices += yields_to_index_rows(yields)

    news = get_news()

    save_to_db(indices, news, yields)
    print("完成")
