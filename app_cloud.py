"""
多市场二级市场数据展板 - Streamlit Cloud 部署版
打开页面自动抓数据，无需本地数据库和定时任务
"""
import streamlit as st
import requests
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="多市场每日数据展板", layout="wide")

# ============ 腾讯财经接口配置 ============
TENCENT_CODES = {
    "sh000001": ("上证指数", "China"),
    "sz399001": ("深证成指", "China"),
    "sz399006": ("创业板指", "China"),
    "sh000300": ("沪深300", "China"),
    "hkHSI":    ("恒生指数", "HK"),
    "hkHSTECH": ("恒生科技指数", "HK"),
}

# ============ 数据抓取函数 ============

@st.cache_data(ttl=3600)
def fetch_tencent_indices():
    """腾讯财经接口 - A股+港股（稳定免费）"""
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
                "volume": 0
            })
        return pd.DataFrame(result)
    except Exception as e:
        st.error(f"行情数据获取失败: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def fetch_global_indices():
    """东方财富全球指数 - 日韩（备选）"""
    targets = [
        {"secid": "100.N225", "name": "日经225", "market": "Japan"},
        {"secid": "100.KS11", "name": "韩国综合指数", "market": "Korea"},
    ]
    result = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    for item in targets:
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
                "market": item["market"],
                "code": item["secid"],
                "name": item["name"],
                "close": round(close, 2),
                "change_pct": round(change_pct, 2),
                "volume": 0
            })
        except Exception:
            pass
    return pd.DataFrame(result)


def get_mock_indices():
    """日韩备用模拟数据"""
    return pd.DataFrame([
        {"market": "Japan", "code": "N225", "name": "日经225", "close": 38500.0, "change_pct": 0.5, "volume": 0},
        {"market": "Korea", "code": "KS11", "name": "韩国综合指数", "close": 2750.0, "change_pct": -0.3, "volume": 0},
    ])


def get_news_data():
    """重要信息 - 实际项目可替换为 RSS/API"""
    today = datetime.now().strftime("%Y-%m-%d")
    data = [
        {"trade_date": today, "time": "09:15", "source": "央行", "title": "今日公开市场开展1000亿元7天期逆回购操作", "content": "维护银行体系流动性合理充裕", "market": "China", "level": 1},
        {"trade_date": today, "time": "11:30", "source": "证监会", "title": "就《上市公司监管指引》公开征求意见", "content": "进一步规范上市公司信息披露行为", "market": "China", "level": 2},
        {"trade_date": today, "time": "14:00", "source": "日经新闻", "title": "日本央行行长暗示年内可能调整宽松政策", "content": "关注通胀持续性和工资增长", "market": "Japan", "level": 1},
        {"trade_date": today, "time": "15:30", "source": "港交所", "title": "港股通今日净买入45亿港元", "content": "科技股获持续加仓", "market": "HK", "level": 2},
    ]
    return pd.DataFrame(data)


# ============ 页面渲染 ============

def main():
    st.title("📊 多市场二级市场数据展板")
    st.caption("每日17:00统一截面 | 中国内地 · 香港 · 日本 · 韩国")

    # 显示数据更新时间
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.caption(f"数据更新时间：{now}（每小时自动刷新）")

    # 抓取数据
    with st.spinner("正在抓取市场数据..."):
        df_tencent = fetch_tencent_indices()
        df_global = fetch_global_indices()

    # 合并数据
    if df_global.empty:
        df_global = get_mock_indices()
        st.info("⚠️ 日韩数据当前为模拟值（接口限流），A股港股为实时数据")

    df_idx = pd.concat([df_tencent, df_global], ignore_index=True)
    df_news = get_news_data()

    if df_idx.empty:
        st.error("数据获取失败，请稍后刷新重试")
        return

    # ============ 第一行：全球市场概览卡片 ============
    st.divider()
    st.subheader("🌍 全球市场概览")

    markets = {"China": "🇨🇳 中国内地", "HK": "🇭🇰 香港", "Japan": "🇯🇵 日本", "Korea": "🇰🇷 韩国"}
    cols = st.columns(4)

    for i, (mkt, label) in enumerate(markets.items()):
        with cols[i]:
            mkt_data = df_idx[df_idx["market"] == mkt]
            if not mkt_data.empty:
                rep = mkt_data.iloc[0]
                delta_color = "normal"  # Streamlit 自动处理正负颜色
                st.metric(
                    label=f"{label} · {rep['name']}",
                    value=f"{rep['close']:.2f}",
                    delta=f"{rep['change_pct']:+.2f}%"
                )
            else:
                st.metric(label=label, value="暂无数据", delta="-")

    # ============ 第二行：分市场详细榜单 ============
    st.divider()
    st.subheader("📋 分市场行情")

    tab1, tab2, tab3, tab4 = st.tabs(["中国内地", "香港", "日本", "韩国"])

    def show_market_table(df, tab):
        with tab:
            if df.empty:
                st.info("暂无数据")
                return
            display = df[["name", "close", "change_pct"]].copy()
            display.columns = ["指数名称", "最新价", "涨跌幅(%)"]
            st.dataframe(display, use_container_width=True, hide_index=True)

    for mkt, tab in zip(["China", "HK", "Japan", "Korea"], [tab1, tab2, tab3, tab4]):
        show_market_table(df_idx[df_idx["market"] == mkt], tab)

    # ============ 第三行：重要信息 ============
    st.divider()
    st.subheader("📰 重要信息")

    if df_news.empty:
        st.info("暂无新闻")
    else:
        for _, row in df_news.iterrows():
            level_color = {1: "🔴", 2: "🟠", 3: "🟢"}.get(row["level"], "⚪")
            with st.container():
                c1, c2 = st.columns([1, 10])
                with c1:
                    st.markdown(f"**{level_color}**")
                with c2:
                    st.markdown(f"**{row['title']}**")
                    st.caption(f"{row['time']} · {row['source']} · 影响市场：{row['market']} | {row['content']}")
                st.divider()

    # ============ 底部说明 ============
    st.divider()
    st.caption("""
    **数据说明**  
    - A股/港股数据来源：腾讯财经（实时）  
    - 日韩数据来源：东方财富（实时）或模拟数据（接口限流时）  
    - 新闻模块当前为演示数据，实际可替换为 RSS/API 抓取  
    - 每小时自动刷新缓存，支持手动刷新页面获取最新数据  
    """)


if __name__ == "__main__":
    main()