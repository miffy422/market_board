"""
Streamlit 多市场数据展板 - 主页面（市场行情 / 盘面总结 / 国债收益率）

「News / 重要信息」已独立为单独页面，见 pages/1_News.py。
共享的数据库读取与渲染组件集中在 common.py。
金融看板风格样式由 styles.py 提供。
"""
import streamlit as st

from styles import inject_styles, render_title, render_section_header, render_kpi_card
from common import (
    ALERT_THRESHOLD,
    MARKETS,
    check_db,
    load_data,
    load_yields,
    render_all_market_change,
    render_industry,
    render_summary,
    render_yields,
    select_date,
    show_table,
)

st.set_page_config(page_title="📊 多市场金融数据看板", layout="wide", page_icon="📊")

# ============ 注入全局样式 ============
inject_styles()

# ============ 页面标题 ============
render_title(
    "多市场金融数据看板",
    "每日 17:00 统一截面 · 中国内地 · 香港 · 日本 · 韩国 · 美国 · 大宗商品",
    tag="LIVE"
)

# ============ 数据库检查 ============
check_db()

# ============ 日期选择器 ============
date_str = select_date(key="home_date")

# ============ 加载数据 ============
df_idx, df_news = load_data(date_str)
df_yields = load_yields(date_str)

if df_idx.empty:
    st.warning(f"⚠️ {date_str} 暂无数据")
    st.stop()

# 显示数据时间
latest_update = df_idx["update_time"].iloc[0] if "update_time" in df_idx.columns else "-"
st.markdown(f'<div class="finance-subtitle">数据时间：{date_str} {latest_update}</div>', unsafe_allow_html=True)

# ============ 全球市场概览卡片 ============
render_section_header("🌍", "全球市场概览")

# 分两行：顶部 6 个市场卡片
cols = st.columns(len(MARKETS))
for i, (mkt, label) in enumerate(MARKETS.items()):
    with cols[i]:
        mkt_data = df_idx[df_idx["market"] == mkt]
        if not mkt_data.empty:
            rep = mkt_data.iloc[0]
            # 用自定义 KPI 卡片替代 st.metric
            kpi_label = f"{label.split(' ')[0]} · {rep['name']}"
            render_kpi_card(
                label=kpi_label,
                value=f"{rep['close']:.2f}",
                delta=f"{rep['change_pct']:+.2f}%"
            )
        else:
            render_kpi_card(label=label, value="—", delta="0.00%")

# ============ 全市场涨跌幅对比 ============
render_section_header("📊", "全市场涨跌幅对比")
render_all_market_change(df_idx, date_str)

# ============ 分市场行情 ============
render_section_header("📋", "分市场行情明细")

tabs = st.tabs(list(MARKETS.values()) + ["🏭 行业板块"])

for i, (mkt, label) in enumerate(MARKETS.items()):
    show_table(df_idx[df_idx["market"] == mkt], tabs[i], mkt, label, date_str)

with tabs[-1]:
    render_industry(df_idx[df_idx["market"] == "CNIndustry"], date_str)

# ============ 当日盘面总结 ============
render_section_header("💡", "当日盘面总结")
render_summary(df_idx, df_news)

# ============ 中美国债收益率曲线 ============
render_section_header("📈", "中美国债收益率曲线与利差")
render_yields(df_yields, date_str)

# ============ 底部说明 ============
st.markdown("""
<style>
.footer-note {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, rgba(6, 182, 212, 0.03) 100%);
    border: 1px solid rgba(59, 130, 246, 0.1);
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    margin-top: 2rem;
    font-size: 0.85rem;
    color: #94a3b8;
    line-height: 1.8;
}
.footer-note strong { color: #3b82f6; }
</style>
<div class="footer-note">
<strong>📌 数据说明</strong><br>
• A股/港股：腾讯财经实时接口 ｜ 日韩/美股/大宗商品：CNBC 行情接口<br>
• 国债收益率（中/美 2Y/5Y/10Y/30Y）：东方财富数据中心（备用源：美国财政部官方 CSV）<br>
• 新闻：东方财富 7×24 快讯（公开接口），详见「News / 重要信息」页面<br>
• 历史数据可追溯，支持日期切换查看 ｜ 图表可下载 PNG，表格可下载 CSV
</div>
""", unsafe_allow_html=True)
