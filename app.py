"""
Streamlit 多市场数据展板 - 主页面（市场行情 / 盘面总结 / 国债收益率）

「News / 重要信息」已独立为单独页面，见 pages/1_News.py。
共享的数据库读取与渲染组件集中在 common.py。
"""
import streamlit as st

from common import (
    ALERT_THRESHOLD,
    MARKETS,
    check_db,
    load_data,
    load_yields,
    render_all_market_change,
    render_summary,
    render_yields,
    select_date,
    show_table,
)

st.set_page_config(page_title="多市场每日数据展板", layout="wide")

# ============ 页面标题 ============
st.title("📊 多市场二级市场数据展板")
st.caption("每日17:00统一截面 | 中国内地 · 香港 · 日本 · 韩国 · 美国 · 大宗商品")

# ============ 数据库检查 ============
check_db()

# ============ 日期选择 ============
date_str = select_date(key="home_date")

# ============ 加载数据 ============
df_idx, df_news = load_data(date_str)
df_yields = load_yields(date_str)

if df_idx.empty:
    st.warning(f"⚠️ {date_str} 暂无数据")
    st.stop()

# 显示数据时间
latest_update = df_idx["update_time"].iloc[0] if "update_time" in df_idx.columns else "-"
st.caption(f"数据更新时间：{date_str} {latest_update}")

# ============ 全球市场概览卡片 ============
st.divider()
st.subheader("🌍 全球市场概览")

cols = st.columns(len(MARKETS))
for i, (mkt, label) in enumerate(MARKETS.items()):
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

# ============ 全市场涨跌幅对比 ============
render_all_market_change(df_idx, date_str)

# ============ 分市场行情 ============
st.divider()
st.subheader("📋 分市场行情")

tabs = st.tabs(list(MARKETS.values()))

for i, (mkt, label) in enumerate(MARKETS.items()):
    show_table(df_idx[df_idx["market"] == mkt], tabs[i], mkt, label, date_str)

# ============ 当日盘面总结 ============
render_summary(df_idx, df_news)

# ============ 中美国债收益率曲线 ============
render_yields(df_yields, date_str)

# ============ 底部 ============
st.divider()
st.caption("""
**数据说明**  
- A股/港股：腾讯财经实时接口  
- 日韩/美股/大宗商品：CNBC 行情接口  
- 国债收益率（中/美 2Y/5Y/10Y/30Y）：东方财富数据中心（备用源：美国财政部官方 CSV）  
- 新闻：东方财富 7×24 快讯（公开接口），见「News / 重要信息」页面  
- 历史数据可追溯，支持日期切换查看  
- 图表可点击图片工具栏中的 📷 按钮下载 PNG；表格可通过下载按钮获取 CSV  
""")
