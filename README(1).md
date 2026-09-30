## 📊 多市场二级市场数据展板 

### 📒 项目简介
<details>
<summary>展开</summary>
    本项目拟建设一套面向研究、投资与管理人员的多市场数据展板。展板以"每日17:00前"为固定信息截面，在同一界面集中呈现中国内地、香港、日本和韩国主要指数的涨跌、成交与市场特征，并同步汇总对二级市场具有实际影响的重要信息，形成可快速浏览、可追溯、可持续更新的日度市场总览。
</details>

### 📄 文件说明
<details>
<summary>展开</summary>

| 文件名 | 作用 |
| :--- | :--- |
| `app.py` | 展板前端页面（Streamlit） |
| `update_data.py` | 数据抓取脚本 |
| `market.db` | 本地数据库文件，存储历史行情和新闻 |
| `requirements.txt` | 依赖清单 |
| `.github/workflows/daily_update.yml` | 自动任务配置，运行 `update_data.py` |

</details>

### 🚀 云端部署（Streamlit Community Cloud）

本项目通过 Streamlit 云端托管，无需本地环境，部署后通过浏览器直接访问。

**① 登录 Streamlit Cloud**

打开 [share.streamlit.io](https://share.streamlit.io)，使用 GitHub 账号授权登录。

**② 创建应用**

点击 **New app**，按以下信息填写：

| 配置项 | 填写内容 |
| :--- | :--- |
| Repository | `https://github.com/miffy422/market_board` |
| Branch | `main` |
| Main file path | `app.py` |
| App URL（自定义，可选） | 例如 `market-board` |

**③ 部署并访问**

点击 **Deploy**，等待 1-2 分钟构建完成，即可通过以下地址访问页面：

```
https://<你的应用名>.streamlit.app
```

**④ 数据更新机制**

仓库中的 `market.db` 随仓库一起部署；GitHub Actions 每日定时运行 `update_data.py` 并自动提交更新，云端页面数据次日自动刷新，无需手动干预。

> 💡 若需立即更新数据，可进入仓库 → **Actions** → **Daily Market Data Update** → **Run workflow** 手动触发，待其完成后在 Streamlit Cloud 页面右上角选择 **Reboot app** 即可。

### 📖 页面功能说明

| 功能 | 说明 |
| :--- | :--- |
| 日期切换 | 左上角下拉框选择历史日期，查看任意交易日的截面数据 |
| 市场概览 | 四大市场代表性指数卡片（最新价 + 涨跌幅） |
| 分市场行情 | 中国内地 / 香港 / 日本 / 韩国四个标签页，含行情表格与涨跌幅柱状图 |
| 图表下载 | 悬停图表，点击右上角工具栏 📷 按钮可下载 PNG 图片 |
| 数据下载 | 每个标签页下方有"下载 CSV"按钮，可用 Excel 直接打开 |
| 重要信息 | 按重要等级分色展示当日新闻，支持一键下载 CSV |
