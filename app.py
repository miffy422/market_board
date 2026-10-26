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


def load_yields(date_str):
    """从数据库读取指定日期的国债收益率明细（yields 表）"""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM yields WHERE trade_date = ?", conn, params=(date_str,)
    )
    conn.close()
    return df


# ============ 页面标题 ============
st.title("📊 多市场二级市场数据展板")
st.caption("每日17:00统一截面 | 中国内地 · 香港 · 日本 · 韩国 · 美国 · 大宗商品")

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
df_yields = load_yields(date_str)

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

markets = {"China": "🇨🇳 中国内地", "HK": "🇭🇰 香港", "Japan": "🇯🇵 日本", "Korea": "🇰🇷 韩国", "US": "🇺🇸 美国", "Commodity": "🛢️ 大宗商品"}
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


def render_yields(yields_df, date_str):
    """中美国债收益率曲线 + 关键利差（10Y-2Y 期限利差、中美国债 10Y 利差）

    数据来自 yields 表，由 update_data.py 抓取东方财富数据中心
    （RPTA_WEB_TREASURYYIELD，备用源：美国财政部官方 CSV）。
    颜色约定沿用展板惯例：收益率上行=红、下行=绿（中国股市配色）。
    """
    st.divider()
    st.subheader("📈 中美国债收益率曲线与利差")

    if yields_df.empty:
        st.info("暂无国债收益率数据（该日期可能未抓取或接口异常）")
        return

    regions = {"CN": "中国", "US": "美国"}
    tenor_order = ["2Y", "5Y", "10Y", "30Y"]
    pivot = yields_df.pivot_table(
        index="tenor", columns="region", values="yield_val"
    ).reindex(tenor_order)

    # ---- 1) 收益率曲线（折线图，中美对比）----
    plot_df = pivot.reset_index().melt(
        id_vars="tenor", value_name="yield_val", var_name="region"
    )
    plot_df["region"] = plot_df["region"].map(regions)
    fig = px.line(
        plot_df, x="tenor", y="yield_val", color="region", markers=True,
        labels={"tenor": "期限", "yield_val": "收益率(%)", "region": "国家"},
        title=f"中美国债收益率曲线（{date_str}）",
        color_discrete_map={"中国": "#ff4d4f", "美国": "#1677ff"},
    )
    fig.update_layout(height=420, xaxis_title="期限", yaxis_title="收益率(%)")
    fig.update_traces(line=dict(width=3))
    st.plotly_chart(fig, use_container_width=True)

    # ---- 2) 关键利差指标卡 ----
    # 2.1 10Y-2Y 期限利差（衰退/复苏信号，<0 即收益率曲线倒挂）
    spread_cards = []
    for region, label in regions.items():
        sub = yields_df[yields_df["region"] == region]
        getv = lambda t: (lambda r: float(r["yield_val"].iloc[0])
                          if not r.empty else None)(sub[sub["tenor"] == t])
        y2, y10 = getv("2Y"), getv("10Y")
        if y2 is not None and y10 is not None:
            spread_cards.append((label, (y10 - y2) * 100))

    # 2.2 中美国债 10Y 利差（影响汇率与跨境资本流动，单位 bp）
    cn10 = pivot.loc["10Y", "CN"] if "CN" in pivot.columns else None
    us10 = pivot.loc["10Y", "US"] if "US" in pivot.columns else None
    cn_us_spread = (us10 - cn10) * 100 if (cn10 is not None and us10 is not None) else None

    card_cols = st.columns(3)
    with card_cols[0]:
        if spread_cards:
            lab, val = spread_cards[0]  # 中国
            inverted = val < 0
            st.metric(
                "中国 10Y-2Y 利差", f"{val:+.0f} bp",
                delta="倒挂(衰退信号)" if inverted else "正常",
                delta_color="inverse" if inverted else "normal",
            )
    with card_cols[1]:
        if len(spread_cards) > 1:
            lab, val = spread_cards[1]  # 美国
            inverted = val < 0
            st.metric(
                "美国 10Y-2Y 利差", f"{val:+.0f} bp",
                delta="倒挂(衰退信号)" if inverted else "正常",
                delta_color="inverse" if inverted else "normal",
            )
    with card_cols[2]:
        if cn_us_spread is not None:
            st.metric(
                "中美国债 10Y 利差", f"{cn_us_spread:+.0f} bp",
                delta="美债高于中债" if cn_us_spread > 0 else "中债高于美债",
                delta_color="inverse" if cn_us_spread > 0 else "normal",
            )

    # ---- 3) 收益率明细表（含日变动 bp）----
    rows = []
    for tenor in tenor_order:
        row = {"期限": tenor}
        cn_r = yields_df[(yields_df["region"] == "CN") & (yields_df["tenor"] == tenor)]
        us_r = yields_df[(yields_df["region"] == "US") & (yields_df["tenor"] == tenor)]
        row["中国收益率(%)"] = round(float(cn_r["yield_val"].iloc[0]), 2) if not cn_r.empty else None
        row["中国变动(bp)"] = round(float(cn_r["chg_bp"].iloc[0]), 1) if not cn_r.empty else None
        row["美国收益率(%)"] = round(float(us_r["yield_val"].iloc[0]), 2) if not us_r.empty else None
        row["美国变动(bp)"] = round(float(us_r["chg_bp"].iloc[0]), 1) if not us_r.empty else None
        row["中美利差(bp)"] = (
            round((float(us_r["yield_val"].iloc[0]) - float(cn_r["yield_val"].iloc[0])) * 100, 1)
            if (not cn_r.empty and not us_r.empty) else None
        )
        rows.append(row)
    detail = pd.DataFrame(rows)

    def color_bp(val):
        if val is None:
            return ""
        color = "#ff4d4f" if val > 0 else "#52c41a" if val < 0 else "black"
        return f"color: {color}; font-weight: bold"

    st.markdown("**收益率明细（较前交易日变动，单位 bp）**")
    styled = detail.style.map(color_bp, subset=["中国变动(bp)", "美国变动(bp)", "中美利差(bp)"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ---- 4) 明细 CSV 下载 ----
    csv = detail.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ 下载国债收益率明细 CSV",
        data=csv,
        file_name=f"yields_{date_str}.csv",
        mime="text/csv",
    )


for i, (mkt, label) in enumerate(markets.items()):
    show_table(df_idx[df_idx["market"] == mkt], tabs[i], mkt, label)

# ============ 当日盘面总结 ============
render_summary(df_idx, df_news)

# ============ 中美国债收益率曲线 ============
render_yields(df_yields, date_str)

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
                st.caption(f"{row['time']} · {row['source']} · 影响：{markets.get(row['market'], row['market'])} | {row['content']}")
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
- 日韩/美股/大宗商品：CNBC 行情接口  
- 国债收益率（中/美 2Y/5Y/10Y/30Y）：东方财富数据中心（备用源：美国财政部官方 CSV）  
- 新闻：东方财富 7×24 快讯（公开接口）  
- 历史数据可追溯，支持日期切换查看  
- 图表可点击图片工具栏中的 📷 按钮下载 PNG；表格可通过下载按钮获取 CSV  
""")

