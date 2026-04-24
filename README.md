# Crypto Admin

一个前后端分离的加密货币数据管理、分析与策略回测平台。支持从币安爬取实时行情与历史 K 线数据，内置多种技术分析指标，集成 DeepSeek AI 交易建议，并提供可视化的策略回测引擎。

---

## 功能特性

| 模块 | 说明 |
|------|------|
| **数据爬取** | 通过 `ccxt` 从币安获取 Ticker 行情、OHLCV K线、订单簿、成交记录，自动追加并去重保存为 CSV |
| **数据查看** | 前端浏览所有本地 CSV 数据文件，支持分页预览表格内容 |
| **定时任务** | 多任务调度器，可按指定周期自动抓取多个交易对数据，支持服务重启后自动恢复 |
| **数据分析** | 自动计算 MA、RSI、MACD、KDJ、布林带、OBV、ATR、WR、CCI 等技术指标，输出完整分析报告 |
| **AI 交易建议** | 可选调用 DeepSeek API，基于技术指标与近期 K 线数据生成做多/做空/观望建议，含开仓价、止盈止损 |
| **策略回测** | 内置双均线交叉策略、RSI 策略，支持自定义参数，输出收益率、夏普比率、胜率、最大回撤等评估指标 |

---

## 技术栈

### 后端
- **FastAPI** — RESTful API 服务
- **ccxt** — 加密货币交易所统一接口（币安数据源）
- **pandas / numpy** — 数据处理与指标计算
- **schedule** — 定时任务调度
- **uvicorn** — ASGI 服务器

### 前端
- **React 19 + TypeScript** — UI 框架
- **Vite** — 构建工具
- **Ant Design** — 组件库
- **Axios** — HTTP 请求
- **Recharts** — 数据可视化图表

---

## 项目结构

```
crypto-admin/
├── backend/
│   ├── data/                     # CSV 数据存储目录
│   ├── api_server.py             # FastAPI 主服务
│   ├── fetch_crypto_data.py      # 数据爬取脚本
│   ├── analyze_data.py           # 数据分析脚本
│   ├── backtest_engine.py        # 回测引擎
│   ├── scheduler.py              # 定时任务脚本
│   ├── scheduler_tasks.json      # 任务持久化配置
│   ├── requirements.txt          # Python 依赖
│   ├── .env.example              # 环境变量模板
│   └── .env                      # 实际环境变量（DeepSeek API Key）
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DataView.tsx      # 数据查看面板
│   │   │   ├── SchedulerPanel.tsx# 定时任务面板
│   │   │   ├── AnalyzePanel.tsx  # 数据分析面板
│   │   │   └── BacktestPanel.tsx # 策略回测面板
│   │   ├── App.tsx               # 主应用与侧边栏导航
│   │   ├── api.ts                # 前端 API 接口封装
│   │   └── ...
│   ├── package.json              # Node 依赖
│   └── vite.config.ts
└── README.md
```

---

## 快速开始

### 1. 克隆项目

```bash
cd crypto-admin
```

### 2. 后端启动

```bash
cd backend

# 创建虚拟环境（可选）
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（如需 DeepSeek AI 分析）
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 启动 API 服务
uvicorn api_server:app --reload --port 8000
```

API 文档默认地址：http://localhost:8000/docs

### 3. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端默认地址：http://localhost:5173

---

## 后端脚本独立使用

除通过前端操作外，各脚本也可在命令行独立运行：

### 爬取数据

```bash
# Ticker 行情
python backend/fetch_crypto_data.py --mode ticker --symbol BTC/USDT

# OHLCV K线（支持 1h / 4h / 1d）
python backend/fetch_crypto_data.py --mode ohlcv --symbol BTC/USDT --timeframe 1h

# 订单簿
python backend/fetch_crypto_data.py --mode orderbook --symbol BTC/USDT

# 成交记录
python backend/fetch_crypto_data.py --mode trades --symbol BTC/USDT
```

### 数据分析

```bash
# 分析指定交易对与周期
python backend/analyze_data.py --symbol BTC/USDT --timeframe 1h

# 分析全部本地数据
python backend/analyze_data.py --all

# 调用 DeepSeek 获取 AI 交易建议
python backend/analyze_data.py --symbol BTC/USDT --timeframe 1h --deepseek
```

### 回测

```python
# 在 Python 中直接调用
from backend.backtest_engine import BacktestEngine, create_strategy

engine = BacktestEngine("backend/data/BTC_USDT_ohlcv_1h.csv")
strategy = create_strategy("sma_cross", short_period=10, long_period=30)
result = engine.run(strategy)
print(result.summary)
```

---

## 核心 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/files` | 列出所有 CSV 数据文件 |
| GET | `/api/files/{filename}` | 读取指定 CSV 内容 |
| POST | `/api/fetch` | 手动触发数据爬取 |
| POST | `/api/analyze` | 手动触发数据分析 |
| GET | `/api/strategies` | 列出可用回测策略 |
| POST | `/api/backtest` | 运行策略回测 |
| POST | `/api/scheduler/tasks` | 创建定时任务 |
| GET | `/api/scheduler/tasks` | 列出所有定时任务 |
| POST | `/api/scheduler/tasks/{id}/stop` | 停止定时任务 |
| DELETE | `/api/scheduler/tasks/{id}` | 删除定时任务 |

---

## 技术分析指标

数据分析模块自动计算以下指标：

- **均线系统**：MA5 / MA7 / MA10 / MA20 / MA30 / MA60，支持多空排列判断与乖离率
- **RSI(14)**：相对强弱指数，识别超买/超卖
- **MACD**：DIF / DEA / 柱状图，金叉死叉信号
- **KDJ**：K / D / J 值，交叉信号
- **布林带(20)**：上轨/中轨/下轨，价格位置与带宽
- **OBV**：能量潮，量价配合判断
- **ATR(14)**：平均真实波幅，衡量波动
- **WR(14)**：威廉指标
- **CCI(20)**：顺势指标
- **支撑阻力**：近期高低点识别
- **多周期动量**：1h / 4h / 24h / 7d 收益率

---

## 回测策略

| 策略名 | 说明 | 可调参数 |
|--------|------|----------|
| `sma_cross` | 双均线交叉策略 | 短期均线周期、长期均线周期 |
| `rsi` | RSI 相对强弱策略 | RSI 周期、超卖线、超买线 |

回测结果包含：总收益率、年化收益率、最大回撤、交易次数、胜率、盈亏比、夏普比率、权益曲线、逐笔交易明细。

---

## 环境变量

在 `backend/.env` 中配置：

```env
DEEPSEEK_API_KEY=your-deepseek-api-key
```

也可通过系统环境变量设置：

```powershell
# Windows PowerShell
$env:DEEPSEEK_API_KEY="your-key"
```

---

## 支持的币种与周期

当前已采集示例数据：

- **交易对**：BTC/USDT、ETH/USDT、SOL/USDT、SUI/USDT、BNB/USDT、DOGE/USDT 等
- **K线周期**：1h、4h、1d
- **其他数据**：Ticker 快照、订单簿、成交记录

通过前端或 API 可自由添加新的交易对与周期组合。
