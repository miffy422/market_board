<img width="1130" height="976" alt="图片" src="https://github.com/user-attachments/assets/49c8f7da-fecd-4026-9775-1672ba5d9b79" /># market_board
多市场二级市场数据展板
1：文件说明
| 文件                                 | 作用                                  | 
| ------------------------------------ | ------------------------------------ |
| `app.py`                             | 展板前端页面                          |
| `update_data.py`                     | 数据抓取脚本                          |
| `market.db`                          | 本地数据库文件，存储历史行情和新闻      |
| `requirements.txt`                   | 依赖清单                              |
| `.github/workflows/daily_update.yml` | 自动任务配置，运行 `update_data.py`    |
