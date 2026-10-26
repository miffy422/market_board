"""
「News（重要信息）」独立页面（Streamlit 多页面：pages/1_News.py）

按重要等级分色展示当日新闻，支持按重要级别与影响市场筛选，并支持 CSV 下载。
"""
import streamlit as st

from common import MARKETS, check_db, load_data, select_date

st.set_page_config(page_title="📰 News", page_icon="📰", layout="wide")

st.title("📰 重要信息")
st.caption("东方财富 7×24 快讯 | 按重要等级分色，可筛选与下载")

# ============ 数据库检查 ============
check_db()

# ============ 日期选择 ============
date_str = select_date(key="news_date")

# ============ 加载数据 ============
_, df_news = load_data(date_str)

st.caption(f"数据日期：{date_str}")

if df_news.empty:
    st.warning(f"⚠️ {date_str} 暂无新闻")
    st.stop()

# ============ 统计 ============
lvl1 = int((df_news["level"] == 1).sum())
lvl2 = int((df_news["level"] == 2).sum())
lvl3 = int((df_news["level"] == 3).sum())
st.markdown(
    f"**当日共 {len(df_news)} 条** ｜ 🔴 高优先级 {lvl1} · 🟠 中 {lvl2} · 🟢 低 {lvl3}"
)

# ============ 筛选器 ============
st.divider()
f_col1, f_col2 = st.columns([1, 2])

with f_col1:
    level_filter = st.radio(
        "重要级别",
        ["全部", "仅 🔴 高优先级"],
        horizontal=True,
        key="news_level_filter",
    )

with f_col2:
    # 影响市场选项：六大市场 + 数据中出现但未映射的市场
    present = sorted(set(df_news["market"].dropna().tolist()))
    options = [MARKETS.get(m, m) for m in present]
    chosen = st.multiselect(
        "影响市场（不选=全部）",
        options=options,
        default=[],
        key="news_market_filter",
    )

# ============ 应用筛选 ============
filtered = df_news.copy()
if level_filter == "仅 🔴 高优先级":
    filtered = filtered[filtered["level"] == 1]
if chosen:
    # 反查回 market 代码（选项为带 emoji 的中文标签）
    label_to_code = {MARKETS.get(m, m): m for m in present}
    codes = [label_to_code[c] for c in chosen]
    filtered = filtered[filtered["market"].isin(codes)]

st.caption(f"筛选结果：{len(filtered)} 条")

# ============ 新闻列表 ============
st.divider()

if filtered.empty:
    st.info("当前筛选条件下没有新闻")
else:
    for _, row in filtered.iterrows():
        level_icon = {1: "🔴", 2: "🟠", 3: "🟢"}.get(row["level"], "⚪")
        with st.container():
            c1, c2 = st.columns([1, 10])
            with c1:
                st.markdown(f"**{level_icon}**")
            with c2:
                st.markdown(f"**{row['title']}**")
                st.caption(
                    f"{row['time']} · {row['source']} · "
                    f"影响：{MARKETS.get(row['market'], row['market'])} | {row['content']}"
                )
            st.divider()

# ============ CSV 下载 ============
if not filtered.empty:
    news_csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ 下载重要信息 CSV",
        data=news_csv,
        file_name=f"news_{date_str}.csv",
        mime="text/csv",
    )
