# 架构文档 —— 代码地图

> **用途**：快速定位每个文件和文件夹的功能，新 AI 或开发者接手时一目了然。
> **更新规则**：每完成一个开发阶段立即更新本文档。
> **配套文档**：
> - `系统架构与后端 PRD 文档.md` — 需求与设计（要做什么）
> - `开发流程与进度核验文档.md` — 进度追踪（做到哪了）
> - `ARCHITECTURE.md` — 代码地图（每个文件干什么的）

> **最后更新**：2026-07-30（阶段 1-5 完成）

---

## 一、项目全景

```
D:\尤里卡\
├── 系统架构与后端 PRD 文档.md          ← 需求与详细设计，开发前先读这个
├── 开发流程与进度核验文档.md            ← 进度清单，切换 AI 时先看这个
├── ARCHITECTURE.md                      ← 本文档，代码地图
└── backend/                             ← 后端项目根目录
    ├── requirements.txt                 ← Python 依赖清单
    ├── .gitignore                       ← Git 忽略规则
    ├── app/                             ← 应用代码（核心）
    │   ├── main.py                      ← 启动入口
    │   ├── core/                        ← 基础设施层
    │   │   ├── config.py                ← 全局配置
    │   │   ├── database.py              ← 数据库连接
    │   │   └── exceptions.py            ← 自定义异常
    │   ├── models/                      ← ORM 数据模型层
    │   │   ├── stocks.py                ← 股票信息表
    │   │   ├── financials.py            ← 财务报表宽表 ★
    │   │   ├── indicators.py            ← 计算指标表
    │   │   └── sync.py                  ← 同步日志 + 披露日历
    │   ├── schemas/                     ← API 请求/响应模型层（待开发）
    │   ├── services/                    ← 业务逻辑层
    │   │   └── etl/                     ← ETL 数据抓取（待开发）
    │   │       ├── fetcher.py           ←   抓取器
    │   │       ├── cleaner.py           ←   清洗器
    │   │       ├── loader.py            ←   入库器
    │   │       ├── scheduler.py         ←   编排器
    │   │       └── column_mapping.py    ←   列名映射
    │   ├── routers/                     ← API 路由层（待开发）
    │   └── utils/                       ← 工具函数层（待开发）
    ├── scripts/                         ← 手动执行脚本
    │   └── init_db.py                   ←   建表 + 预置数据
    ├── data/                            ← 运行时数据（不提交 Git）
    │   ├── eureka.db                    ←   SQLite 数据库文件
    │   └── cache/                       ←   diskcache 缓存目录
    └── tests/                           ← 测试代码（待开发）
```

---

## 二、文件功能详解

### 2.1 根目录文件

| 文件 | 功能 | 谁在用 |
|------|------|--------|
| `requirements.txt` | Python 依赖声明，`pip install -r` 一键安装 | 部署 / 新环境初始化 |
| `.gitignore` | 忽略 `__pycache__`、`.db`、`data/cache`、`.env` | Git |

---

### 2.2 `app/` — 应用代码入口

#### `app/main.py` — FastAPI 启动入口

**职责**：
- 创建 FastAPI app 实例（`title="Eureka Stock Analyzer"`）
- 注册 CORS 中间件（开发阶段放行所有来源）
- 注册启动事件 `on_startup`：自动调用 `Base.metadata.create_all()` 建表
- 注册健康检查路由：`GET /` 和 `GET /api/v1/health`
- 注册全部 6 个全局异常处理器

**路由清单**（当前已实现）：

| 路径 | 方法 | 功能 | 状态 |
|------|------|------|------|
| `/` | GET | 健康检查 | ✅ |
| `/api/v1/health` | GET | 健康检查 | ✅ |
| `/docs` | GET | Swagger 自动文档 | ✅ 自动 |
| `/redoc` | GET | ReDoc 自动文档 | ✅ 自动 |

**异常处理映射**：

| 异常类 | HTTP 状态码 | 含义 |
|--------|------------|------|
| `AppBaseException` | 400 | 所有自定义异常的基类 |
| `DataFetchException` | 502 | 外部数据源不可用 |
| `StockNotFoundException` | 404 | 股票代码不存在 |
| `DataValidationException` | 422 | 数据校验失败 |
| `ScreeningExpressionError` | 400 | 筛选表达式语法错误 |
| `ValuationParameterError` | 400 | 估值参数不合法 |
| `Exception` (兜底) | 500 | 未预期的服务器内部错误 |

---

### 2.3 `app/core/` — 基础设施层

这一层的代码**不涉及业务逻辑**，只提供项目运行所需的底层能力。其他所有模块都依赖这一层。

#### `app/core/config.py` — 全局配置中心

**职责**：集中管理所有可调参数，通过环境变量或 `.env` 文件覆盖。

**配置分类**：

| 分类 | 配置项（部分列举） | 默认值 |
|------|-------------------|--------|
| 数据库 | `DATABASE_URL` | `sqlite:///./data/eureka.db` |
| 缓存 | `CACHE_DIR`, `CACHE_TTL_HISTORICAL` | `./data/cache`, 21600s |
| ETL 限速 | `ETL_RATE_LIMIT_CALLS`, `ETL_MIN_INTERVAL` | 4次/秒, 0.5s |
| ETL 重试 | `ETL_RETRY_ATTEMPTS`, `ETL_RETRY_MIN_WAIT` | 5次, 1s |
| 数据抓取 | `DEFAULT_FETCH_YEARS`, `ETL_BATCH_SIZE` | 5年, 50只/批 |
| API 限流 | `RATE_LIMIT_PUBLIC`, `RATE_LIMIT_HEAVY` | 100次/分, 30次/分 |
| 鉴权 | `WECHAT_APP_ID`, `JWT_SECRET_KEY` | 空, 占位 |
| 服务器 | `HOST`, `PORT`, `DEBUG` | `0.0.0.0`, 8000, true |

**使用方式**：
```python
from app.core.config import settings
print(settings.DATABASE_URL)  # 全局单例，随时取用
```

#### `app/core/database.py` — 数据库连接管理

**职责**：
- 创建 SQLAlchemy `engine`（自动启用 SQLite WAL 模式 + 外键约束）
- 创建 `SessionLocal` 会话工厂
- 声明 `Base` 基类（所有 ORM 模型继承它）
- 提供 `get_db()` FastAPI 依赖注入函数

**关键细节**：
- WAL 模式：允许"一边写入一边读取"，不阻塞
- `check_same_thread=False`：允许 FastAPI 异步线程跨线程使用 SQLite
- `pool_pre_ping=True`：每次使用前检查连接是否存活

**使用方式**：
```python
# 在路由中
@app.get("/stocks")
def list_stocks(db: Session = Depends(get_db)):
    return db.query(Stock).all()
```

#### `app/core/exceptions.py` — 自定义异常体系

**职责**：定义 6 个业务异常类，每种对应一个已知的错误场景。

**异常层级**：
```
AppBaseException               ← 所有业务异常的基类
├── DataFetchException         ← 数据源不可用
├── StockNotFoundException     ← 股票不存在
├── DataValidationException    ← 数据校验失败
├── ScreeningExpressionError   ← 筛选表达式错误
└── ValuationParameterError    ← 估值参数错误
```

**使用方式**：
```python
from app.core.exceptions import StockNotFoundException
raise StockNotFoundException(symbol="999999")
# → HTTP 404: {"code":404, "message":"股票代码不存在: 999999"}
```

---

### 2.4 `app/models/` — ORM 数据模型层

这一层定义了数据库**每张表的结构**。每个 Python 类 = 数据库中的一张表。

#### `app/models/stocks.py` — 股票信息表

**表名**：`stocks`
**行含义**：一只 A 股上市公司
**字段数**：10

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | String(10) PK | 股票代码 |
| `name` | String(50) | 股票简称 |
| `market` | String(2) | SH/SZ/BJ |
| `industry` | String(50) | 申万一级行业 |
| `sub_industry` | String(50) | 申万二级行业 |
| `list_date` | Date | 上市日期 |
| `is_active` | Boolean | 是否上市 |
| `total_shares` | Numeric(20,2) | 总股本 |

#### `app/models/financials.py` — 财务报表宽表 ★ 核心

**表名**：`financial_statements`
**行含义**：一只股票在一个报表期的完整财报
**字段数**：77
**唯一约束**：`(symbol, report_date, report_type)` — 同一只股票的同一期报表不会重复

**字段分组**：

| 分组 | 字段数 | 举例 |
|------|--------|------|
| 元数据 | 7 | `symbol`, `report_date`, `report_type`, `fiscal_year`, `data_source` |
| 资产负债表-资产 | 16 | `total_assets`, `cash_and_equivalents`, `inventory`, `fixed_assets`, `goodwill` |
| 资产负债表-负债 | 12 | `total_liabilities`, `short_term_borrowings`, `long_term_borrowings` |
| 资产负债表-权益 | 6 | `total_equity`, `retained_earnings`, `minority_interest` |
| 利润表 | 21 | `operating_revenue`, `net_profit_attr_parent`, `basic_eps`, `r_and_d_expenses` |
| 现金流量表 | 12 | `net_operating_cashflow`, `capital_expenditure`, `ending_cash_balance` |
| 审计字段 | 2 | `created_at`, `updated_at` |

> **数据精度**：利润表和现金流量表使用 akshare 的 `_by_quarterly_em` 接口，直接获取单季度独立数据。资产负债表使用 `_by_report_em`，本身就是时点快照。每行数据代表该报表期内的独立经营成果，四个季度之和 = 全年值。

#### `app/models/indicators.py` — 计算指标表

**表名**：`financial_indicators`
**行含义**：一条 `financial_statements` 对应的计算比率
**字段数**：29

| 分组 | 字段数 | 举例 |
|------|--------|------|
| 盈利能力 | 5 | `roe`, `roa`, `gross_margin`, `net_margin`, `operating_margin` |
| 成长能力 | 4 | `revenue_yoy`, `net_profit_yoy`, `operating_profit_yoy`, `eps_yoy` |
| 偿债与流动性 | 5 | `current_ratio`, `quick_ratio`, `debt_to_assets`, `debt_to_equity`, `interest_coverage` |
| 营运效率 | 3 | `asset_turnover`, `inventory_turnover`, `receivable_turnover` |
| 估值相关 | 3 | `fcf`, `dividend_per_share`, `book_value_per_share` |
| 单季度值 | 3 | `revenue_single_q`, `net_profit_single_q`, `operating_cashflow_single_q` |

#### `app/models/sync.py` — 同步日志 + 财报日历

**表 1**：`sync_log` (10 字段) — 每次 ETL 数据同步的执行记录
**表 2**：`reporting_calendar` (6 字段) — A 股四个披露窗口的截止日参考，已预置 2024-2026 共 12 条数据

---

### 2.5 `app/services/etl/` — ETL 数据抓取服务层 ★ 已实现

这一层是项目最复杂的部分，负责从外部数据源抓取真实 A 股财报数据、清洗、入库。

#### `app/services/etl/column_mapping.py` — 列名映射表

**职责**：维护 akshare 东方财富 API 返回的英文缩写列名 → 数据库英文字段名的映射。三张报表各一份映射字典，共 80+ 条。

**实际列名格式**：akshare 返回的列名是英文缩写（如 `TOTAL_ASSETS`、`PARENT_NETPROFIT`），不是中文。每个指标还伴有 `_YOY` 后缀的同比列，这些列被忽略（增长率由 loader 自行计算）。

#### `app/services/etl/fetcher.py` — 数据抓取器

**职责**：封装 akshare 调用，实现四层防御体系：

| 层级 | 机制 | 实现 |
|------|------|------|
| L1 限速 | Token Bucket，0.5-1.5s 随机间隔 | `@rate_limited` 装饰器 |
| L2 重试 | 5次指数退避（1s→60s） | `tenacity` 库 |
| L3 缓存 | 历史数据 6h，实时数据 30min | `diskcache` |
| L4 备用源 | 东方财富 → 新浪财经 | `_try_fallback()` |

**数据源选择**：
- 资产负债表：`stock_balance_sheet_by_report_em`（时点快照，无需季度版）
- 利润表：`stock_profit_sheet_by_quarterly_em`（单季度数据，非累积）
- 现金流量表：`stock_cash_flow_sheet_by_quarterly_em`（单季度数据）

#### `app/services/etl/cleaner.py` — 数据清洗器

**职责**：6 步清洗流水线——
1. 列名映射（英文缩写 → 数据库字段名）
2. 单位检测与统一（万元→元）
3. 空值处理（NaN → None）
4. 日期解析 + report_type 推断（12-31→annual, 03-31→q1, 06-30→semi_annual, 09-30→q3）
5. 添加元数据列（symbol, data_source, currency）
6. 数据校验（总资产>0，会计恒等式 < 1%偏差）
7. 三表合并为宽表行

#### `app/services/etl/loader.py` — 数据入库器

**职责**：
- `upsert_stocks()`：批量 upsert 股票信息（ON CONFLICT UPDATE）
- `upsert_financials()`：批量 upsert 合并后的宽表数据
- `compute_and_store_indicators()`：自动计算 20+ 个财务指标并写入 `financial_indicators` 表，包括：
  - 盈利能力（ROE、ROA、毛利率、净利率、营业利润率）
  - 成长能力（营收/利润/EPS 同比增长率，通过 prev_map 对比上年同期）
  - 偿债与流动性（流动比率、速动比率、资产负债率、利息保障倍数）
  - 营运效率（总资产周转率）
  - 估值相关（自由现金流 FCF、每股净资产）

#### `app/services/etl/scheduler.py` — ETL 编排器

**职责**：协调 fetcher → cleaner → loader 全流程，支持全量同步（`sync_all_stocks`）和增量同步（`incremental_sync`，框架已就绪）。异常处理保证单只股票失败不中断整体流程。

---

### 2.6 `scripts/` — 手动执行脚本

#### `scripts/init_db.py` — 数据库初始化

**用法**：
```bash
python scripts/init_db.py            # 建表
python scripts/init_db.py --drop     # 删除重建
python scripts/init_db.py --seed     # 建表 + 预置财报日历
python scripts/init_db.py --drop --seed  # 完全重置
```

**执行流程**：
1. 导入所有 ORM 模型 → 注册到 `Base.metadata`
2. 调用 `Base.metadata.create_all(engine)` → 自动建表
3. 可选：预置 2024-2026 年度财报披露截止日（12 条数据）

#### `scripts/run_etl.py` — 数据抓取工具

**用法**：
```bash
python scripts/run_etl.py                              # 全量同步（5000只，4-8h）
python scripts/run_etl.py --symbols 600519,000858       # 指定股票
python scripts/run_etl.py --years 3                     # 仅最近3年
python scripts/run_etl.py --symbols 600519 --dry-run   # 调试：只抓不存
```

**数据精度**：每条记录是该报表期的独立数据。资产负债表为时点快照，利润表和现金流量表为单季度值，四个季度之和 = 年报值。

---

### 2.6 `data/` — 运行时数据（不提交 Git）

| 路径 | 内容 |
|------|------|
| `data/eureka.db` | SQLite 数据库文件，包含所有业务数据 |
| `data/cache/` | diskcache 缓存目录，缓存 akshare 返回的原始数据 |

---

## 三、数据流全景（当前 + 规划）

```
┌─────────────────────────────────────────────────────────┐
│                    外部数据源                               │
│  东方财富 (Eastmoney) ─── 新浪财经 (Sina) ─── 备用          │
└─────────────────┬───────────────────────────────────────┘
                  │ akshare 库封装
                  ▼
┌─────────────────────────────────────────────────────────┐
│                   ETL 模块 (已完成)                         │
│  fetcher.py → cleaner.py → loader.py → scheduler.py       │
│  四层防御抓取   六步清洗        upsert+指标   全量/增量编排   │
│  单季度数据 ✅  日期推断 ✅    20+指标计算 ✅  容错处理 ✅    │
└─────────────────┬───────────────────────────────────────┘
                  │ upsert
                  ▼
┌─────────────────────────────────────────────────────────┐
│                   数据库层 (已完成)                         │
│  stocks  ←──  financial_statements  ←──  financial_indicators │
│  股票信息       原始财报数据 (77列)        计算比率 (29列)    │
│                 sync_log (审计)    reporting_calendar (日历)  │
└─────────────────┬───────────────────────────────────────┘
                  │ SQLAlchemy ORM
                  ▼
┌─────────────────────────────────────────────────────────┐
│                   API 层 (阶段4)                           │
│  routers/stocks.py  routers/financials.py  routers/data.py │
│  股票查询              财务数据查询           同步管理        │
└─────────────────┬───────────────────────────────────────┘
                  │ JSON over HTTPS
                  ▼
┌─────────────────────────────────────────────────────────┐
│                  微信小程序前端                             │
│  wx.request() → 展示数据、筛选、估值                        │
└─────────────────────────────────────────────────────────┘
```

---

## 四、当前文件清单（阶段 1 + 2 + 3 完成时）

```
backend/
├── requirements.txt           ✅
├── .gitignore                 ✅
├── app/
│   ├── __init__.py            ✅
│   ├── main.py                ✅ FastAPI 入口 + CORS + 5 路由模块
│   ├── core/
│   │   ├── __init__.py        ✅
│   │   ├── config.py          ✅ 30+ 配置项
│   │   ├── database.py        ✅ SQLAlchemy 引擎 (WAL) + Session
│   │   └── exceptions.py      ✅ 6 个业务异常类
│   ├── models/
│   │   ├── __init__.py        ✅
│   │   ├── stocks.py          ✅ 10 字段
│   │   ├── financials.py      ✅ 77 字段 (核心宽表)
│   │   ├── indicators.py      ✅ 29 字段 (计算指标)
│   │   └── sync.py            ✅ SyncLog + ReportingCalendar
│   ├── schemas/
│   │   ├── __init__.py        ✅
│   │   ├── common.py          ✅ APIResponse + PaginatedData
│   │   ├── stocks.py          ✅ StockSummary + StockDetail
│   │   ├── financials.py      ✅ FinancialRecord + IndicatorMeta
│   │   ├── screener.py        ✅ FilterCondition + ScreenerRequest
│   │   └── valuation.py       ✅ DCF/DDM Request + Response
│   ├── services/
│   │   ├── __init__.py        ✅
│   │   ├── etl/
│   │   │   ├── __init__.py    ✅
│   │   │   ├── column_mapping.py ✅ 80+ 条 akshare 列名映射
│   │   │   ├── fetcher.py     ✅ 四层防御 + 单季度数据抓取
│   │   │   ├── cleaner.py     ✅ 六步清洗 + 三表合并
│   │   │   ├── loader.py      ✅ upsert + 年报指标计算(四季汇总)
│   │   │   └── scheduler.py   ✅ 全量/增量同步编排
│   │   ├── screener.py        ✅ 条件解析 + SQL编译 + 连续N年
│   │   └── valuation.py       ✅ DCF/DDM 两阶段 + 自动填充
│   ├── routers/
│   │   ├── __init__.py        ✅
│   │   ├── stocks.py          ✅ 股票列表 + 详情
│   │   ├── financials.py      ✅ 财务历史 + 指标列表
│   │   ├── data.py            ✅ 同步触发 + 状态
│   │   ├── screener.py        ✅ 多条件选股
│   │   └── valuation.py       ✅ DCF + DDM 估值
│   └── utils/
│       └── __init__.py        ✅ (空)
├── scripts/
│   ├── init_db.py             ✅ 建表 + 预置财报日历
│   └── run_etl.py             ✅ 命令行 ETL 工具
├── data/
│   └── .gitkeep               ✅
└── tests/
    └── __init__.py            ✅ (空)
```

---

> **下一阶段（阶段 4）新增文件**：
> - `app/schemas/common.py` — 通用响应包装 (APIResponse, PaginatedData)
> - `app/schemas/stocks.py` — 股票相关 Pydantic 模型
> - `app/schemas/financials.py` — 财务数据 Pydantic 模型
> - `app/routers/stocks.py` — 股票查询 API
> - `app/routers/financials.py` — 财务数据 API
> - `app/routers/data.py` — 数据同步 API
