"""
Streamlit 多市场数据展板 - 读取本地/仓库中的 SQLite
"""
import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta

import plotly.express as px

st.set_page_config(page_title="多市场每日数据展板", layout="wide")

DB_PATH = "market.db"
ALERT_THRESHOLD = 2.0  # 异常波动预警阈值（涨跌幅绝对值，单位 %）


def load_data(date_str):
    """从数据库读取指定日期"""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame(), pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    df_idx = pd.read_sql_query(
        "SELECT * FROM indices WHERE trade_date = ? ORDER BY market, change_pct DESC",
        conn, params=(date_str,)
    )
    df_news = pd.read_sql_query(
        "SELECT * FROM news WHERE trade_date = ? ORDER BY level, time",
        conn, params=(date_str,)
    )
    conn.close()
    return df_idx, df_news


def get_available_dates():
    """获取数据库中所有有数据的日期"""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    dates = pd.read_sql_query(
        "SELECT DISTINCT trade_date FROM indices ORDER BY trade_date DESC",
        conn
    )["trade_date"].tolist()
    conn.close()
    return dates


# ============ 页面标题 ============
st.title("📊 多市场二级市场数据展板")
st.caption("每日17:00统一截面 | 中国内地 · 香港 · 日本 · 韩国 · 美国")

# ============ 数据库检查 ============
if not os.path.exists(DB_PATH):
    st.error("⚠️ 数据库文件 `market.db` 不存在")
    st.info("""
    **解决方法：**
    1. **本地测试**：在文件夹里运行 `python update_data.py` 生成数据库
    2. **线上部署**：等待 GitHub Actions 每日自动更新（首次次日生效）
    3. **手动触发**：进入 GitHub 仓库 → Actions → Daily Market Data Update → Run workflow
    """)
    st.stop()

# ============ 日期选择 ============
available_dates = get_available_dates()
today = datetime.now().strftime("%Y-%m-%d")

col1, col2 = st.columns([1, 4])
with col1:
    if available_dates:
        selected = st.selectbox("选择日期", available_dates, index=0)
    else:
        selected = st.date_input("选择日期", datetime.now())
        selected = selected.strftime("%Y-%m-%d")

date_str = selected

# ============ 加载数据 ============
df_idx, df_news = load_data(date_str)

if df_idx.empty:
    st.warning(f"⚠️ {date_str} 暂无数据")
    if date_str == today:
        st.info("今日数据尚未生成，请稍后再试或手动触发 GitHub Actions")
    else:
        st.info("该日期无历史数据")
    st.stop()

# 显示数据时间
latest_update = df_idx["update_time"].iloc[0] if "update_time" in df_idx.columns else "-"
st.caption(f"数据更新时间：{date_str} {latest_update}")

# ============ 全球市场概览卡片 ============
st.divider()
st.subheader("🌍 全球市场概览")

markets = {"China": "🇨🇳 中国内地", "HK": "🇭🇰 香港", "Japan": "🇯🇵 日本", "Korea": "🇰🇷 韩国", "US": "🇺🇸 美国"}
cols = st.columns(len(markets))

for i, (mkt, label) in enumerate(markets.items()):
    with cols[i]:
        mkt_data = df_idx[df_idx["market"] == mkt]
        if not mkt_data.empty:
            rep = mkt_data.iloc[0]
            st.metric(
                label=f"{label} · {rep['name']}",
                value=f"{rep['close']:.2f}",
                delta=f"{rep['change_pct']:+.2f}%"
            )
        else:
            st.metric(label=label, value="暂无", delta="-")

# ============ 分市场行情 ============
st.divider()
st.subheader("📋 分市场行情")

tabs = st.tabs(list(markets.values()))


def show_table(df, tab, mkt, mkt_label):
    with tab:
        if df.empty:
            st.info("暂无数据")
            return
        display = df[["name", "close", "change_pct"]].copy()
        display["异动"] = display["change_pct"].apply(
            lambda v: "⚠️" if abs(v) >= ALERT_THRESHOLD else ""
        )
        display.columns = ["指数名称", "最新价", "涨跌幅(%)", "异动"]

        def color_pct(val):
            color = "#ff4d4f" if val > 0 else "#52c41a" if val < 0 else "black"
            return f"color: {color}; font-weight: bold"

        st.dataframe(
            display.style.map(color_pct, subset=["涨跌幅(%)"]),
            use_container_width=True, hide_index=True
        )

        # ---- 新增：图表（Plotly 自带工具栏可下载 PNG）----
        fig = px.bar(
            display, x="指数名称", y="涨跌幅(%)",
            title=f"{mkt_label} 指数涨跌幅（{date_str}）",
            color="涨跌幅(%)",
            color_continuous_scale=["#52c41a", "#d9d9d9", "#ff4d4f"],
            color_continuous_midpoint=0,
            text="涨跌幅(%)",
        )
        fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        fig.update_layout(coloraxis_showscale=False, height=400)
        st.plotly_chart(fig, use_container_width=True)

        # ---- 新增：CSV 下载按钮 ----
        csv = display.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label=f"⬇️ 下载{mkt_label}行情 CSV",
            data=csv,
            file_name=f"market_{mkt}_{date_str}.csv",
            mime="text/csv",
        )


def render_summary(df_idx, df_news):
    """当日盘面智能总结（规则引擎 v1）：全市场广度 + 各市场领涨领跌 + 新闻统计 + 异常波动预警。"""
    st.subheader("📊 当日盘面总结")
    if df_idx.empty:
        st.info("暂无行情数据")
        return
    up = int((df_idx["change_pct"] > 0).sum())
    down = int((df_idx["change_pct"] < 0).sum())
    flat = int((df_idx["change_pct"] == 0).sum())
    st.markdown(
        f"**全市场广度**：🟥 上涨 {up} · 🟩 下跌 {down} · ➖ 平 {flat}"
        f"（共 {len(df_idx)} 个指数）"
    )
    lines = []
    for mkt, label in markets.items():
        sub = df_idx[df_idx["market"] == mkt]
        if sub.empty:
            continue
        top = sub.loc[sub["change_pct"].idxmax()]
        bot = sub.loc[sub["change_pct"].idxmin()]
        lines.append(
            f"- {label}：领涨 **{top['name']} {top['change_pct']:+.2f}%**，"
            f"领跌 **{bot['name']} {bot['change_pct']:+.2f}%**"
        )
    if lines:
        st.markdown("\n".join(lines))
    if not df_news.empty:
        lvl1 = int((df_news["level"] == 1).sum())
        st.markdown(f"**重要信息**：共 {len(df_news)} 条，其中 🔴 高优先级 {lvl1} 条")
    flagged = df_idx[df_idx["change_pct"].abs() >= ALERT_THRESHOLD]
    if not flagged.empty:
        items = "、".join(
            f"{r['name']} {r['change_pct']:+.2f}%" for _, r in flagged.iterrows()
        )
        st.error(f"⚠️ **异常波动预警**（|涨跌幅| ≥ {ALERT_THRESHOLD:.0f}%）：{items}")
    else:
        st.success(f"✅ 当日无异常波动（阈值 {ALERT_THRESHOLD:.0f}%）")


for i, (mkt, label) in enumerate(markets.items()):
    show_table(df_idx[df_idx["market"] == mkt], tabs[i], mkt, label)

# ============ 当日盘面总结 ============
render_summary(df_idx, df_news)

# ============ 重要信息 ============
st.divider()
st.subheader("📰 重要信息")

if df_news.empty:
    st.info("暂无新闻")
else:
    for _, row in df_news.iterrows():
        level_icon = {1: "🔴", 2: "🟠", 3: "🟢"}.get(row["level"], "⚪")
        with st.container():
            c1, c2 = st.columns([1, 10])
            with c1:
                st.markdown(f"**{level_icon}**")
            with c2:
                st.markdown(f"**{row['title']}**")
                st.caption(f"{row['time']} · {row['source']} · 影响：{row['market']} | {row['content']}")
            st.divider()

# ---- 新增：重要信息下载 ----
if not df_news.empty:
    news_csv = df_news.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ 下载重要信息 CSV",
        data=news_csv,
        file_name=f"news_{date_str}.csv",
        mime="text/csv",
    )

# ============ 底部 ============
st.divider()
st.caption("""
**数据说明**  
- A股/港股：腾讯财经实时接口  
- 日韩/美股：CNBC 行情接口  
- 新闻：东方财富 7×24 快讯（公开接口）  
- 历史数据可追溯，支持日期切换查看  
- 图表可点击图片工具栏中的 📷 按钮下载 PNG；表格可通过下载按钮获取 CSV  
""")
