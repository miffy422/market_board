"""
「News（重要信息）」独立页面（Streamlit 多页面：pages/1_News.py）

按重要等级分色展示当日新闻，支持按重要级别与影响市场筛选，并支持 CSV 下载。
"""
import streamlit as st

from styles import inject_styles, render_title, render_section_header, render_news_card
from common import MARKETS, check_db, load_data, select_date

st.set_page_config(page_title="📰 重要信息", page_icon="📰", layout="wide")

# ============ 注入全局样式 ============
inject_styles()

# ============ 页面标题 ============
render_title(
    "重要信息中心",
    "东方财富 7×24 快讯 · 按重要等级分类",
    tag="LIVE"
)

# ============ 数据库检查 ============
check_db()

# ============ 日期选择 ============
date_str = select_date(key="news_date")

# ============ 加载数据 ============
_, df_news = load_data(date_str)

st.markdown(f'<div class="finance-subtitle">数据日期：{date_str}</div>', unsafe_allow_html=True)

if df_news.empty:
    st.warning(f"⚠️ {date_str} 暂无新闻")
    st.stop()

# ============ 统计面板 ============
lvl1 = int((df_news["level"] == 1).sum())
lvl2 = int((df_news["level"] == 2).sum())
lvl3 = int((df_news["level"] == 3).sum())

st.markdown(f"""
<style>
.stats-row {{
    display: flex; gap: 1rem; margin: 1rem 0 2rem 0; flex-wrap: wrap;
}}
.stats-chip {{
    display: inline-flex; align-items: center; gap: 0.5rem;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    padding: 0.6rem 1rem;
    font-size: 0.9rem;
    font-weight: 600;
}}
.stats-chip.total {{ color: var(--text-primary); border-color: var(--border-accent); }}
.stats-chip.lvl1 {{ color: var(--up-red); border-left: 3px solid var(--up-red); }}
.stats-chip.lvl2 {{ color: var(--warning-amber); border-left: 3px solid var(--warning-amber); }}
.stats-chip.lvl3 {{ color: var(--accent-cyan); border-left: 3px solid var(--accent-cyan); }}
.stats-num {{
    font-family: 'SF Mono', 'JetBrains Mono', monospace;
    font-size: 1.1rem;
}}
</style>
<div class="stats-row">
    <div class="stats-chip total">📊 总计 <span class="stats-num">{len(df_news)}</span> 条</div>
    <div class="stats-chip lvl1">🔴 高优先级 <span class="stats-num">{lvl1}</span></div>
    <div class="stats-chip lvl2">🟠 中优先级 <span class="stats-num">{lvl2}</span></div>
    <div class="stats-chip lvl3">🟢 低优先级 <span class="stats-num">{lvl3}</span></div>
</div>
""", unsafe_allow_html=True)

# ============ 筛选器 ============
render_section_header("🔍", "筛选条件")

f_col1, f_col2 = st.columns([1, 2])

with f_col1:
    level_filter = st.radio(
        "重要级别",
        ["全部", "仅 🔴 高优先级"],
        horizontal=True,
        key="news_level_filter",
    )

with f_col2:
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
    label_to_code = {MARKETS.get(m, m): m for m in present}
    codes = [label_to_code[c] for c in chosen]
    filtered = filtered[filtered["market"].isin(codes)]

st.markdown(f'<div class="finance-subtitle">筛选结果：{len(filtered)} 条</div>', unsafe_allow_html=True)

# ============ 新闻列表 ============
render_section_header("📰", "新闻列表")

if filtered.empty:
    st.info("当前筛选条件下没有新闻")
else:
    for _, row in filtered.iterrows():
        render_news_card(row)

# ============ CSV 下载 ============
if not filtered.empty:
    news_csv = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="⬇️ 下载筛选结果 CSV",
        data=news_csv,
        file_name=f"news_{date_str}.csv",
        mime="text/csv",
    )
