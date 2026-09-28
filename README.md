## 📊 多市场二级市场数据展板 

### 📚 项目简介
<details>
<summary>展开</summary>
    本项目拟建设一套面向研究、投资与管理人员的多市场数据展板。展板以"每日17:00前"为固定信息截面，在同一界面集中呈现中国内地、香港、日本和韩国主要指数的涨跌、成交与市场特征，并同步汇总对二级市场具有实际影响的重要信息，形成可快速浏览、可追溯、可持续更新的日度市场总览。
</details>

### 📄 文件说明

<details>
<summary>展开</summary>
  
| 文件名 | 作用 |
| :--- | :--- |
| `app.py` | 展板前端页面 |
| `update_data.py` | 数据抓取脚本 |
| `market.db` | 本地数据库文件，存储历史行情和新闻 |
| `requirements.txt` | 依赖清单 |
| `.github/workflows/daily_update.yml` | 自动任务配置，运行 `update_data.py` |

</details>
