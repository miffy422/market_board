"""
共享数据与渲染组件
供主页面 app.py 与 pages/ 下的独立页面（如「News / 重要信息」）复用，
避免多页面之间重复实现数据库读取与图表渲染逻辑。
"""
import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.express as px

DB_PATH = "market.db"
ALERT_THRESHOLD = 2.0  # 异常波动预警阈值（涨跌幅绝对值，单位 %）

# 六大市场（概览卡片 / 分市场标签页 / 盘面总结 / 全市场对比图均由此动态驱动）
MARKETS = {
    "China": "🇨🇳 中国内地",
    "HK": "🇭🇰 香港",
    "Japan": "🇯🇵 日本",
    "Korea": "🇰🇷 韩国",
    "US": "🇺🇸 美国",
    "Commodity": "🛢️ 大宗商品",
}

# 仅含五大股市（大宗商品在「分市场行情」标签页单独展示，不混入全市场涨跌幅对比图）
STOCK_MARKETS = {k: v for k, v in MARKETS.items() if k != "Commodity"}


# ============ 数据读取 ============
def check_db():
    """数据库不存在时给出指引并终止当前页面渲染"""
    if not os.path.exists(DB_PATH):
        st.error("⚠️ 数据库文件 `market.db` 不存在")
        st.info("""
        **解决方法：**
        1. **本地测试**：在文件夹里运行 `python update_data.py` 生成数据库
        2. **线上部署**：等待 GitHub Actions 每日自动更新（首次次日生效）
        3. **手动触发**：进入 GitHub 仓库 → Actions → Daily Market Data Update → Run workflow
        """)
        st.stop()


def get_available_dates():
    """获取数据库中所有有数据的日期"""
    conn = sqlite3.connect(DB_PATH)
    dates = pd.read_sql_query(
        "SELECT DISTINCT trade_date FROM indices ORDER BY trade_date DESC",
        conn
    )["trade_date"].tolist()
    conn.close()
    return dates


def load_data(date_str):
    """从数据库读取指定日期的行情与新闻"""
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


def load_yields(date_str):
    """从数据库读取指定日期的国债收益率明细（yields 表）"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM yields WHERE trade_date = ?", conn, params=(date_str,)
    )
    conn.close()
    return df


def select_date(key="date_select"):
    """日期选择下拉框（各页面独立选择，互不影响）"""
    available_dates = get_available_dates()
    if available_dates:
        selected = st.selectbox("选择日期", available_dates, index=0, key=key)
    else:
        selected = st.date_input("选择日期", datetime.now(), key=key)
        selected = selected.strftime("%Y-%m-%d")
    return selected


# ============ 渲染组件 ============
def color_pct(val):
    """涨跌幅配色：涨=红、跌=绿（中国股市惯例）"""
    color = "#ff4d4f" if val > 0 else "#52c41a" if val < 0 else "black"
    return f"color: {color}; font-weight: bold"


def _bar_fig(display, mkt_label, date_str):
    """各市场当日涨跌幅柱状图（红涨绿跌）"""
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
    return fig


def render_trend(end_date, mkt, n_days=5):
    """某市场各指数「近几日涨跌幅」走势（折线图数据源）

    返回以 trade_date 为索引、各指数为列的透视表；
    若截至 end_date 的历史交易日不足 2 天则返回 None（调用方回退柱状图）。
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        dates = pd.read_sql_query(
            "SELECT DISTINCT trade_date FROM indices "
            "WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT ?",
            conn, params=(end_date, n_days)
        )["trade_date"].tolist()
        if len(dates) < 2:
            return None
        dates_sorted = sorted(dates)
        qmarks = ",".join("?" * len(dates_sorted))
        df = pd.read_sql_query(
            f"SELECT trade_date, name, change_pct FROM indices "
            f"WHERE market=? AND trade_date IN ({qmarks})",
            conn, params=(mkt,) + tuple(dates_sorted)
        )
    finally:
        conn.close()
    if df.empty:
        return None
    return df.pivot_table(index="trade_date", columns="name", values="change_pct")


def show_table(df, tab, mkt, mkt_label, date_str):
    """单个市场的行情表格 + 近5日涨跌幅折线图 + CSV 下载

    所有市场统一展示「近5日涨跌幅折线图」（多指数走势）；
    历史数据不足 2 个交易日时回退为当日柱状图。
    """
    with tab:
        if df.empty:
            st.info("暂无数据")
            return
        display = df[["name", "close", "change_pct"]].copy()
        display["异动"] = display["change_pct"].apply(
            lambda v: "⚠️" if abs(v) >= ALERT_THRESHOLD else ""
        )
        display.columns = ["指数名称", "最新价", "涨跌幅(%)", "异动"]

        st.dataframe(
            display.style.map(color_pct, subset=["涨跌幅(%)"]),
            use_container_width=True, hide_index=True
        )

        pivot = render_trend(date_str, mkt)
        if pivot is not None and not pivot.empty and len(pivot) >= 2:
            plot_df = pivot.reset_index().melt(
                id_vars="trade_date", var_name="指数", value_name="涨跌幅(%)"
            )
            fig = px.line(
                plot_df, x="trade_date", y="涨跌幅(%)", color="指数",
                markers=True,
                title=f"{mkt_label} 涨跌幅走势（近 {len(pivot)} 日）",
                labels={"trade_date": "日期", "涨跌幅(%)": "涨跌幅(%)", "指数": "指数"},
            )
            fig.add_hline(y=0, line_width=1, line_color="#999999")
            fig.update_layout(height=420)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("历史数据不足（需 ≥2 个交易日），以下为当日柱状图")
            st.plotly_chart(_bar_fig(display, mkt_label, date_str), use_container_width=True)

        csv = display.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label=f"⬇️ 下载{mkt_label}行情 CSV",
            data=csv,
            file_name=f"market_{mkt}_{date_str}.csv",
            mime="text/csv",
        )


def render_all_market_change(df_idx, date_str):
    """各市场涨跌幅横向条形对比

    提供两种视角：
      1. 按指数：全部品种横向条形排序，条形方向表示涨跌（向右涨/向左跌），
         按中国惯例红涨绿跌着色，市场名前缀区分所属市场；
      2. 按市场：每个市场一根条形（该市场各指数涨跌幅均值）。
    注：仅含五大股市；大宗商品涨跌幅在「分市场行情」标签页单独展示，
    国债利差行的 change_pct 口径与价格涨跌幅不同，另见国债收益率区块。
    """
    st.divider()
    st.subheader("📊 全市场涨跌幅对比")

    if df_idx.empty:
        st.info("暂无行情数据")
        return

    base = df_idx[df_idx["market"].isin(STOCK_MARKETS.keys())].copy()
    if base.empty:
        st.info("暂无可对比的市场行情")
        return
    base["市场"] = base["market"].map(MARKETS)

    view = st.radio(
        ["按指数（全部品种）", "按市场（平均涨跌幅）"],
        horizontal=True,
        key="all_change_view",
    )

    scale = ["#52c41a", "#d9d9d9", "#ff4d4f"]  # 绿 → 灰 → 红

    if view.startswith("按指数"):
        plot_df = base[["name", "市场", "change_pct"]].copy()
        plot_df["名称"] = plot_df["市场"] + " · " + plot_df["name"]
        # 横向条形图中数据框靠前的项在下方，故升序排序可让涨幅最大的显示在顶部
        plot_df = plot_df.sort_values("change_pct", ascending=True)
        fig = px.bar(
            plot_df, x="change_pct", y="名称", orientation="h",
            color="change_pct",
            color_continuous_scale=scale,
            color_continuous_midpoint=0,
            text="change_pct",
            title=f"全市场涨跌幅对比 · 按指数（{date_str}）",
            labels={"change_pct": "涨跌幅(%)", "名称": ""},
        )
        fig.update_traces(texttemplate="%{text:+.2f}%", textposition="outside")
        fig.update_layout(
            coloraxis_showscale=False,
            height=max(420, 26 * len(plot_df) + 140),
        )
    else:
        agg = base.groupby("市场", as_index=False)["change_pct"].mean()
        agg = agg.sort_values("change_pct", ascending=True)
        fig = px.bar(
            agg, x="change_pct", y="市场", orientation="h",
            color="change_pct",
            color_continuous_scale=scale,
            color_continuous_midpoint=0,
            text="change_pct",
            title=f"各市场平均涨跌幅（{date_str}）",
            labels={"change_pct": "平均涨跌幅(%)", "市场": ""},
        )
        fig.update_traces(texttemplate="%{text:+.2f}%", textposition="outside")
        fig.update_layout(coloraxis_showscale=False, height=420)

    fig.add_vline(x=0, line_width=1, line_color="#999999")
    st.plotly_chart(fig, use_container_width=True)


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
    for mkt, label in MARKETS.items():
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
    if df_news is not None and not df_news.empty:
        lvl1 = int((df_news["level"] == 1).sum())
        st.markdown(
            f"**重要信息**：共 {len(df_news)} 条，其中 🔴 高优先级 {lvl1} 条"
            f"（详见左侧「News / 重要信息」页面）"
        )
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
    spread_cards = []
    for region, label in regions.items():
        sub = yields_df[yields_df["region"] == region]

        def getv(t):
            r = sub[sub["tenor"] == t]
            return float(r["yield_val"].iloc[0]) if not r.empty else None

        y2, y10 = getv("2Y"), getv("10Y")
        if y2 is not None and y10 is not None:
            spread_cards.append((label, (y10 - y2) * 100))

    cn10 = pivot.loc["10Y", "CN"] if "CN" in pivot.columns else None
    us10 = pivot.loc["10Y", "US"] if "US" in pivot.columns else None
    cn_us_spread = (us10 - cn10) * 100 if (cn10 is not None and us10 is not None) else None

    card_cols = st.columns(3)
    with card_cols[0]:
        if spread_cards:
            _, val = spread_cards[0]  # 中国
            inverted = val < 0
            st.metric(
                "中国 10Y-2Y 利差", f"{val:+.0f} bp",
                delta="倒挂(衰退信号)" if inverted else "正常",
                delta_color="inverse" if inverted else "normal",
            )
    with card_cols[1]:
        if len(spread_cards) > 1:
            _, val = spread_cards[1]  # 美国
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

    st.markdown("**收益率明细（较前交易日变动，单位 bp）**")
    styled = detail.style.map(color_pct, subset=["中国变动(bp)", "美国变动(bp)", "中美利差(bp)"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ---- 4) 明细 CSV 下载 ----
    csv = detail.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ 下载国债收益率明细 CSV",
        data=csv,
        file_name=f"yields_{date_str}.csv",
        mime="text/csv",
    )

