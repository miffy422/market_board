"""
金融看板风格样式系统
参照 Bloomberg Terminal / Wind / 同花顺 等专业金融终端的深色科技设计
"""

# ===== 全局 CSS：深色金融看板主题 =====
GLOBAL_CSS = """
<style>
/* ============ 基础变量 ============ */
:root {
    --bg-primary: #0a0f1a;
    --bg-secondary: #111827;
    --bg-card: rgba(17, 24, 39, 0.85);
    --bg-card-hover: rgba(30, 41, 59, 0.9);
    --border-subtle: rgba(59, 130, 246, 0.15);
    --border-accent: rgba(59, 130, 246, 0.4);
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent-blue: #3b82f6;
    --accent-cyan: #06b6d4;
    --up-red: #ef4444;
    --up-red-glow: rgba(239, 68, 68, 0.3);
    --down-green: #22c55e;
    --down-green-glow: rgba(34, 197, 94, 0.3);
    --warning-amber: #f59e0b;
    --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.4);
    --shadow-glow: 0 0 20px rgba(59, 130, 246, 0.15);
    --gradient-primary: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
    --gradient-card: linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(6, 182, 212, 0.05) 100%);
}

/* ============ 全局背景 ============ */
.stApp {
    background: var(--bg-primary);
    background-image: 
        radial-gradient(ellipse 80% 50% at 50% -20%, rgba(59, 130, 246, 0.08), transparent),
        radial-gradient(ellipse 60% 40% at 0% 100%, rgba(6, 182, 212, 0.05), transparent);
}

/* ============ 侧边栏美化 ============ */
[data-testid="stSidebar"] {
    background: var(--bg-secondary) !important;
    border-right: 1px solid var(--border-subtle);
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 2rem;
}

/* ============ 主容器 ============ */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 1600px !important;
}

/* ============ 页面主标题 ============ */
.finance-title {
    font-size: 2.2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #f1f5f9 0%, #3b82f6 50%, #06b6d4 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.25rem;
    letter-spacing: -0.02em;
}
.finance-subtitle {
    font-size: 0.95rem;
    color: var(--text-muted);
    letter-spacing: 0.05em;
}

/* ============ 分区标题 ============ */
.section-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 2rem 0 1rem 0;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border-subtle);
}
.section-header-icon {
    font-size: 1.3rem;
    filter: drop-shadow(0 0 8px rgba(59, 130, 246, 0.5));
}
.section-header-text {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: 0.02em;
}
.section-header-line {
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, var(--border-accent) 0%, transparent 100%);
}

/* ============ 指标卡片（替代 st.metric） ============ */
.kpi-card {
    background: var(--bg-card);
    backdrop-filter: blur(12px);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: var(--gradient-primary);
    opacity: 0.6;
}
.kpi-card:hover {
    border-color: var(--border-accent);
    box-shadow: var(--shadow-glow);
    transform: translateY(-2px);
}
.kpi-card.up::before { background: linear-gradient(90deg, transparent, var(--up-red), transparent); opacity: 0.8; }
.kpi-card.down::before { background: linear-gradient(90deg, transparent, var(--down-green), transparent); opacity: 0.8; }

.kpi-label {
    font-size: 0.78rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.5rem;
}
.kpi-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--text-primary);
    font-family: 'SF Mono', 'JetBrains Mono', ui-monospace, monospace;
    letter-spacing: -0.02em;
}
.kpi-delta {
    font-size: 0.95rem;
    font-weight: 600;
    margin-top: 0.35rem;
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.15rem 0.6rem;
    border-radius: 6px;
}
.kpi-delta.up { color: var(--up-red); background: rgba(239, 68, 68, 0.12); }
.kpi-delta.down { color: var(--down-green); background: rgba(34, 197, 94, 0.12); }
.kpi-delta.flat { color: var(--text-muted); background: rgba(100, 116, 139, 0.15); }

/* ============ 面板容器 ============ */
.panel {
    background: var(--bg-card);
    backdrop-filter: blur(12px);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 1.25rem;
    margin: 0.75rem 0;
}
.panel-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* ============ 新闻卡片 ============ */
.news-card {
    background: var(--bg-card);
    backdrop-filter: blur(8px);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin: 0.6rem 0;
    transition: all 0.25s ease;
    border-left: 3px solid transparent;
}
.news-card:hover {
    border-color: var(--border-accent);
    background: var(--bg-card-hover);
    transform: translateX(4px);
}
.news-card.level-1 { border-left-color: var(--up-red); }
.news-card.level-2 { border-left-color: var(--warning-amber); }
.news-card.level-3 { border-left-color: var(--accent-cyan); }

.news-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.35rem;
}
.news-meta {
    font-size: 0.78rem;
    color: var(--text-muted);
    display: flex;
    gap: 1rem;
    align-items: center;
    flex-wrap: wrap;
}
.news-badge {
    display: inline-block;
    padding: 0.1rem 0.5rem;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.news-badge.level-1 { background: rgba(239, 68, 68, 0.2); color: var(--up-red); }
.news-badge.level-2 { background: rgba(245, 158, 11, 0.2); color: var(--warning-amber); }
.news-badge.level-3 { background: rgba(6, 182, 212, 0.2); color: var(--accent-cyan); }

/* ============ Streamlit 原生组件覆盖 ============ */
/* 标题 */
h1, h2, h3, h4, h5, h6 { color: var(--text-primary) !important; }
h1 { font-weight: 700 !important; letter-spacing: -0.02em; }
h2 { font-weight: 600 !important; }

/* 分割线 */
hr, [data-testid="stDivider"] {
    border-color: var(--border-subtle) !important;
    background: var(--border-subtle) !important;
}

/* 指标值 */
[data-testid="stMetricValue"] {
    font-family: 'SF Mono', 'JetBrains Mono', ui-monospace, monospace !important;
}
[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    backdrop-filter: blur(8px);
    border: 1px solid var(--border-subtle) !important;
    border-radius: 10px !important;
    padding: 1rem !important;
}
[data-testid="stMetricLabel"] { color: var(--text-secondary) !important; }

/* 下拉框 & 选择框 */
.stSelectbox > div > div, .stMultiSelect > div > div, .stTextInput > div > div {
    background: var(--bg-secondary) !important;
    border-color: var(--border-subtle) !important;
    color: var(--text-primary) !important;
}
.stSelectbox > div > div:hover, .stMultiSelect > div > div:hover {
    border-color: var(--border-accent) !important;
}

/* Radio / Checkbox */
.stRadio [role="radiogroup"] label, .stCheckbox label {
    color: var(--text-secondary) !important;
}

/* 按钮 */
.stButton > button, [data-testid="baseButton-secondary"] {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-subtle) !important;
    color: var(--text-primary) !important;
    border-radius: 8px !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover, [data-testid="baseButton-secondary"]:hover {
    background: var(--bg-card-hover) !important;
    border-color: var(--border-accent) !important;
    box-shadow: var(--shadow-glow);
}
[data-testid="baseButton-primary"] {
    background: var(--gradient-primary) !important;
    border: none !important;
    border-radius: 8px !important;
    color: white !important;
}

/* Tab */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.25rem;
    border-bottom: 1px solid var(--border-subtle);
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-secondary) !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.2s ease;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text-primary) !important; }
.stTabs [aria-selected="true"] {
    background: var(--bg-card) !important;
    color: var(--accent-blue) !important;
    border: 1px solid var(--border-accent) !important;
    border-bottom-color: transparent !important;
}

/* 表格 */
[data-testid="stDataFrame"] > div > div {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 10px !important;
    overflow: hidden;
}
[data-testid="stDataFrame"] table thead th {
    background: rgba(59, 130, 246, 0.1) !important;
    color: var(--text-primary) !important;
    font-weight: 600 !important;
}
[data-testid="stDataFrame"] table tbody tr:hover {
    background: rgba(59, 130, 246, 0.08) !important;
}

/* Container */
[data-testid="stContainer"] {
    background: transparent !important;
}

/* Caption */
.stMarkdown p, .caption, [data-testid="stCaptionContainer"] {
    color: var(--text-secondary) !important;
}

/* Warning/Success/Info boxes */
[data-testid="stAlert"] {
    background: var(--bg-card) !important;
    backdrop-filter: blur(8px);
    border: 1px solid var(--border-subtle) !important;
    border-radius: 10px !important;
}

/* 下载按钮 */
.stDownloadButton > button {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-subtle) !important;
    color: var(--accent-cyan) !important;
    border-radius: 8px !important;
}
.stDownloadButton > button:hover {
    background: rgba(6, 182, 212, 0.15) !important;
    border-color: var(--accent-cyan) !important;
}

/* ============ 滚动条 ============ */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--bg-secondary); }
::-webkit-scrollbar-thumb { background: var(--border-subtle); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--border-accent); }

/* ============ 动画 ============ */
@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); }
    50% { box-shadow: 0 0 0 8px rgba(59, 130, 246, 0); }
}
.pulse-dot {
    width: 8px; height: 8px;
    background: #22c55e;
    border-radius: 50%;
    animation: pulse-glow 2s ease-in-out infinite;
    display: inline-block;
}
</style>
"""

# ===== 注入全局样式的辅助函数 =====
def inject_styles():
    """在页面入口调用，注入全局 CSS"""
    import streamlit as st
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ===== 金融看板风格的组件生成器 =====
def render_title(title_text, subtitle_text="", tag="LIVE"):
    """生成金融看板风格的页面主标题"""
    import streamlit as st
    tag_html = ""
    if tag:
        tag_html = f'''
        <span style="
            display: inline-flex; align-items: center; gap: 0.4rem;
            background: rgba(34, 197, 94, 0.15); color: #22c55e;
            padding: 0.15rem 0.6rem; border-radius: 20px;
            font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em;
            border: 1px solid rgba(34, 197, 94, 0.3);
            margin-left: 0.75rem; vertical-align: middle;
        ">
            <span class="pulse-dot"></span>{tag}
        </span>'''
    st.markdown(f'<div class="finance-title">{title_text}{tag_html}</div>', unsafe_allow_html=True)
    if subtitle_text:
        st.markdown(f'<div class="finance-subtitle">{subtitle_text}</div>', unsafe_allow_html=True)


def render_section_header(icon, text):
    """生成统一风格的分区标题"""
    import streamlit as st
    st.markdown(f'''
    <div class="section-header">
        <span class="section-header-icon">{icon}</span>
        <span class="section-header-text">{text}</span>
        <span class="section-header-line"></span>
    </div>
    ''', unsafe_allow_html=True)


def render_kpi_card(label, value, delta=None):
    """生成 KPI 指标卡片（替代 st.metric）"""
    import streamlit as st
    # 判断涨跌方向
    direction = "flat"
    delta_html = ""
    if delta is not None:
        try:
            d = float(str(delta).replace("%", "").replace("+", ""))
            if d > 0:
                direction = "up"
                delta_html = f'<span class="kpi-delta up">▲ {delta}</span>'
            elif d < 0:
                direction = "down"
                delta_html = f'<span class="kpi-delta down">▼ {delta}</span>'
            else:
                delta_html = f'<span class="kpi-delta flat">— 0.00%</span>'
        except (ValueError, TypeError):
            delta_html = f'<span class="kpi-delta flat">{delta}</span>'
    st.markdown(f'''
    <div class="kpi-card {direction}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {delta_html}
    </div>
    ''', unsafe_allow_html=True)


def render_news_card(row):
    """生成新闻卡片"""
    import streamlit as st
    level = row.get("level", 3)
    level_class = f"level-{level}"
    level_label = {1: "重要", 2: "一般", 3: "参考"}.get(level, "参考")
    market = row.get("market", "")
    source = row.get("source", "")
    time_val = row.get("time", "")
    title = row.get("title", "")
    content = row.get("content", "")

    st.markdown(f'''
    <div class="news-card {level_class}">
        <div class="news-title">{title}</div>
        <div class="news-meta">
            <span class="news-badge {level_class}">{level_label}</span>
            <span>⏱️ {time_val}</span>
            <span>📰 {source}</span>
            <span>💹 {market}</span>
        </div>
        {f'<div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.5rem; line-height: 1.5;">{content}</div>' if content else ''}
    </div>
    ''', unsafe_allow_html=True)
