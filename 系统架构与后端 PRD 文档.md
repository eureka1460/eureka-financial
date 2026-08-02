# A股财报选股与估值小程序 —— 系统架构与后端开发文档 (Backend PRD)

> **文档版本**：v2.0
> **适用对象**：后端开发者、AI 编程助手
> **项目定位**：基于开源数据的高性能、轻量级 A 股财报数据拉取、自定义条件筛选及估值模型计算后端 API 服务。

---

## 目录

1. [系统整体架构与技术选型](#1-系统整体架构与技术选型)
2. [数据库结构设计](#2-数据库结构设计)
3. [ETL 数据抓取与清洗](#3-etl-数据抓取与清洗)
4. [核心 API 路由定义](#4-核心-api-路由定义)
5. [筛选引擎设计](#5-筛选引擎设计)
6. [估值模型设计](#6-估值模型设计)
7. [鉴权方案](#7-鉴权方案)
8. [非功能性需求](#8-非功能性需求)
9. [项目目录结构](#9-项目目录结构)
10. [数据更新策略](#10-数据更新策略)

---

## 1. 系统整体架构与技术选型

### 1.1 架构图

```
[数据源: AKShare (Eastmoney 为主, Sina 为备)]
       │ (Python ETL，每季度定期 + 手动触发)
       ▼
[本地数据库: SQLite (开发) / PostgreSQL (生产)]
       │ (FastAPI RESTful API, JSON over HTTPS)
       ▼
[后端 HTTP 服务]
       │ (wx.request)
       ▼
[微信小程序前端]
```

### 1.2 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | |
| Web 框架 | FastAPI | 异步高性能，自动生成 OpenAPI 文档 |
| 数据源 | akshare >= 2.0.0 | 开源免费，封装东方财富/新浪财经接口 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） | 通过 SQLAlchemy 无缝切换 |
| ORM | SQLAlchemy 2.x + Alembic | 数据库迁移管理 |
| 数据处理 | Pandas + NumPy | ETL 数据清洗与计算 |
| 缓存 | diskcache | 请求缓存，减少重复抓取 |
| 重试 | tenacity | 指数退避重试 |
| 参数校验 | Pydantic v2 | 请求/响应模型校验 |

### 1.3 数据传输规范

- **协议**：HTTPS（生产）/ HTTP（本地开发）
- **格式**：全量 API 交互采用标准 JSON，编码 UTF-8
- **统一响应结构**：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

- **分页响应结构**：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [],
    "total": 5000,
    "page": 1,
    "page_size": 20
  }
}
```

- **错误响应结构**：

```json
{
  "code": 404,
  "message": "股票代码不存在",
  "detail": "symbol '999999' not found"
}
```

---

## 2. 数据库结构设计

> **设计原则**：采用宽表模式存储财务报表，一张大表覆盖资产负债表、利润表、现金流量表的全部核心字段。另有独立的计算指标表和 ETL 审计日志表。

### 2.1 股票信息表 `stocks`

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| symbol | VARCHAR(10) | PK | 股票代码，如 '600519' |
| name | VARCHAR(50) | NOT NULL | 股票简称，如 '贵州茅台' |
| market | VARCHAR(2) | NOT NULL | 交易所：'SH'(上海) / 'SZ'(深圳) / 'BJ'(北交所) |
| industry | VARCHAR(50) | | 申万一级行业分类 |
| sub_industry | VARCHAR(50) | | 申万二级行业分类 |
| list_date | DATE | | 上市日期 |
| is_active | BOOLEAN | DEFAULT TRUE | 是否仍上市（剔除退市股） |
| total_shares | NUMERIC(20,2) | | 总股本（用于计算每股指标和估值） |
| created_at | DATETIME | DEFAULT NOW | 创建时间 |
| updated_at | DATETIME | DEFAULT NOW | 最后更新时间 |

**索引**：`idx_stocks_industry` ON (industry)，`idx_stocks_name` ON (name)

---

### 2.2 财务报表表 `financial_statements`（核心宽表）

> 每行 = 一只股票在一个报表期的一份完整财报。
> 
> **重要说明**：akshare 返回的利润表和现金流量表数据为**年初至今累积值(YTD)**。例如 Q3 的 operating_revenue 表示 1-9 月的总和。后端的 `financial_indicators` 表会额外存储推导出的**单季度值**。

| 分类 | 字段名 | 类型 | 说明 |
|------|--------|------|------|
| **元数据** |
| | id | INTEGER | 主键，自增 |
| | symbol | VARCHAR(10) | FK → stocks.symbol |
| | report_date | DATE | 报表截止日，如 '2024-12-31' |
| | report_type | VARCHAR(20) | 'annual' / 'semi_annual' / 'q1' / 'q3' |
| | fiscal_year | INTEGER | 会计年度，如 2024 |
| | currency | VARCHAR(10) | 默认 'CNY' |
| | data_source | VARCHAR(50) | 'eastmoney' / 'sina' |
| **资产负债表 — 资产** |
| | total_assets | NUMERIC(28,2) | 总资产 |
| | current_assets | NUMERIC(28,2) | 流动资产合计 |
| | cash_and_equivalents | NUMERIC(28,2) | 货币资金 |
| | trading_financial_assets | NUMERIC(28,2) | 交易性金融资产 |
| | notes_receivable | NUMERIC(28,2) | 应收票据 |
| | accounts_receivable | NUMERIC(28,2) | 应收账款 |
| | prepayments | NUMERIC(28,2) | 预付款项 |
| | other_receivables | NUMERIC(28,2) | 其他应收款 |
| | inventory | NUMERIC(28,2) | 存货 |
| | non_current_assets | NUMERIC(28,2) | 非流动资产合计 |
| | fixed_assets | NUMERIC(28,2) | 固定资产 |
| | construction_in_progress | NUMERIC(28,2) | 在建工程 |
| | intangible_assets | NUMERIC(28,2) | 无形资产 |
| | goodwill | NUMERIC(28,2) | 商誉 |
| | long_term_equity_investments | NUMERIC(28,2) | 长期股权投资 |
| | deferred_tax_assets | NUMERIC(28,2) | 递延所得税资产 |
| **资产负债表 — 负债** |
| | total_liabilities | NUMERIC(28,2) | 总负债 |
| | current_liabilities | NUMERIC(28,2) | 流动负债合计 |
| | short_term_borrowings | NUMERIC(28,2) | 短期借款 |
| | notes_payable | NUMERIC(28,2) | 应付票据 |
| | accounts_payable | NUMERIC(28,2) | 应付账款 |
| | contract_liabilities | NUMERIC(28,2) | 合同负债 |
| | employee_payable | NUMERIC(28,2) | 应付职工薪酬 |
| | taxes_payable | NUMERIC(28,2) | 应交税费 |
| | non_current_liabilities | NUMERIC(28,2) | 非流动负债合计 |
| | long_term_borrowings | NUMERIC(28,2) | 长期借款 |
| | bonds_payable | NUMERIC(28,2) | 应付债券 |
| | deferred_tax_liabilities | NUMERIC(28,2) | 递延所得税负债 |
| **资产负债表 — 权益** |
| | total_equity | NUMERIC(28,2) | 所有者权益合计 |
| | paid_in_capital | NUMERIC(28,2) | 实收资本（股本） |
| | capital_reserve | NUMERIC(28,2) | 资本公积 |
| | surplus_reserve | NUMERIC(28,2) | 盈余公积 |
| | retained_earnings | NUMERIC(28,2) | 未分配利润 |
| | minority_interest | NUMERIC(28,2) | 少数股东权益 |
| **利润表**（年初至今累积值 YTD） |
| | operating_revenue | NUMERIC(28,2) | 营业总收入 |
| | operating_cost | NUMERIC(28,2) | 营业总成本 |
| | selling_expenses | NUMERIC(28,2) | 销售费用 |
| | administrative_expenses | NUMERIC(28,2) | 管理费用 |
| | r_and_d_expenses | NUMERIC(28,2) | 研发费用 |
| | financial_expenses | NUMERIC(28,2) | 财务费用 |
| | interest_expense | NUMERIC(28,2) | 利息费用 |
| | investment_income | NUMERIC(28,2) | 投资收益 |
| | fair_value_change | NUMERIC(28,2) | 公允价值变动收益 |
| | asset_impairment_loss | NUMERIC(28,2) | 资产减值损失 |
| | credit_impairment_loss | NUMERIC(28,2) | 信用减值损失 |
| | taxes_and_surcharges | NUMERIC(28,2) | 税金及附加 |
| | operating_profit | NUMERIC(28,2) | 营业利润 |
| | total_profit | NUMERIC(28,2) | 利润总额 |
| | income_tax_expense | NUMERIC(28,2) | 所得税费用 |
| | net_profit | NUMERIC(28,2) | 净利润（含少数股东） |
| | net_profit_attr_parent | NUMERIC(28,2) | 归母净利润 |
| | net_profit_excl_nonrecurring | NUMERIC(28,2) | 扣非归母净利润 |
| | minority_profit | NUMERIC(28,2) | 少数股东损益 |
| | basic_eps | NUMERIC(18,4) | 基本每股收益 |
| | diluted_eps | NUMERIC(18,4) | 稀释每股收益 |
| | other_comprehensive_income | NUMERIC(28,2) | 其他综合收益 |
| **现金流量表**（年初至今累积值 YTD） |
| | net_operating_cashflow | NUMERIC(28,2) | 经营活动现金流净额 |
| | cash_from_sales | NUMERIC(28,2) | 销售商品提供劳务收到的现金 |
| | cash_paid_to_employees | NUMERIC(28,2) | 支付给职工及为职工支付的现金 |
| | taxes_paid | NUMERIC(28,2) | 支付的各项税费 |
| | net_investing_cashflow | NUMERIC(28,2) | 投资活动现金流净额 |
| | capital_expenditure | NUMERIC(28,2) | 购建固定资产无形资产支付的现金（资本支出） |
| | net_financing_cashflow | NUMERIC(28,2) | 筹资活动现金流净额 |
| | cash_from_borrowings | NUMERIC(28,2) | 取得借款收到的现金 |
| | dividends_paid | NUMERIC(28,2) | 分配股利、偿付利息支付的现金 |
| | net_change_in_cash | NUMERIC(28,2) | 现金及现金等价物净增加额 |
| | beginning_cash_balance | NUMERIC(28,2) | 期初现金及现金等价物余额 |
| | ending_cash_balance | NUMERIC(28,2) | 期末现金及现金等价物余额 |
| **记录元数据** |
| | created_at | DATETIME | DEFAULT NOW |
| | updated_at | DATETIME | DEFAULT NOW |

**唯一约束**：`UNIQUE(symbol, report_date, report_type)`

**索引**：`idx_fs_symbol`, `idx_fs_report_date`, `idx_fs_fiscal_year`, `idx_fs_type`

---

### 2.3 计算指标表 `financial_indicators`

> 在 ETL 入库后自动计算并写入。所有比率型指标和同比增速统一在此表，避免筛选查询时重复计算。

| 分类 | 字段名 | 类型 | 说明 |
|------|--------|------|------|
| **元数据** |
| | id | INTEGER | 主键，自增 |
| | symbol | VARCHAR(10) | FK → stocks.symbol |
| | report_date | DATE | 报表截止日 |
| | report_type | VARCHAR(20) | 报表类型 |
| | fiscal_year | INTEGER | 会计年度 |
| **盈利能力** |
| | roe | NUMERIC(12,6) | 净资产收益率 = 归母净利润 / 平均净资产 |
| | roa | NUMERIC(12,6) | 总资产收益率 = 净利润 / 平均总资产 |
| | gross_margin | NUMERIC(12,6) | 毛利率 = (营收-营业成本) / 营收 |
| | net_margin | NUMERIC(12,6) | 净利率 = 归母净利润 / 营收 |
| | operating_margin | NUMERIC(12,6) | 营业利润率 = 营业利润 / 营收 |
| **成长能力（同比增速）** |
| | revenue_yoy | NUMERIC(12,6) | 营收同比增长率 |
| | net_profit_yoy | NUMERIC(12,6) | 归母净利润同比增长率 |
| | operating_profit_yoy | NUMERIC(12,6) | 营业利润同比增长率 |
| | eps_yoy | NUMERIC(12,6) | EPS 同比增长率 |
| **偿债与流动性** |
| | current_ratio | NUMERIC(12,6) | 流动比率 = 流动资产 / 流动负债 |
| | quick_ratio | NUMERIC(12,6) | 速动比率 = (货币资金+应收) / 流动负债 |
| | debt_to_assets | NUMERIC(12,6) | 资产负债率 = 总负债 / 总资产 |
| | debt_to_equity | NUMERIC(12,6) | 权益乘数 = 总负债 / 总权益 |
| | interest_coverage | NUMERIC(12,6) | 利息保障倍数 = 营业利润 / 利息费用 |
| **营运效率** |
| | asset_turnover | NUMERIC(12,6) | 总资产周转率 = 营收 / 平均总资产 |
| | inventory_turnover | NUMERIC(12,6) | 存货周转率 |
| | receivable_turnover | NUMERIC(12,6) | 应收账款周转率 |
| **估值相关** |
| | fcf | NUMERIC(28,2) | 自由现金流 = 经营现金流净额 - 资本支出 |
| | dividend_per_share | NUMERIC(18,4) | 每股股利 |
| | book_value_per_share | NUMERIC(18,4) | 每股净资产 |
| **单季度值**（从累积值推导） |
| | revenue_single_q | NUMERIC(28,2) | 单季度营业收入 |
| | net_profit_single_q | NUMERIC(28,2) | 单季度归母净利润 |
| | operating_cashflow_single_q | NUMERIC(28,2) | 单季度经营现金流 |
| **元数据** |
| | created_at | DATETIME | DEFAULT NOW |

**唯一约束**：`UNIQUE(symbol, report_date, report_type)`

---

### 2.4 ETL 同步日志表 `sync_log`

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INTEGER | 主键，自增 |
| job_type | VARCHAR(50) | 'full_sync' / 'incremental_sync' / 'metadata_refresh' |
| status | VARCHAR(20) | 'running' / 'success' / 'failed' / 'partial' |
| stocks_total | INTEGER | 待同步股票总数 |
| stocks_synced | INTEGER | 成功同步数 |
| stocks_failed | INTEGER | 失败数 |
| reports_fetched | INTEGER | 抓取到的报表行数 |
| error_details | TEXT | 错误详情 JSON |
| started_at | DATETIME | 开始时间 |
| completed_at | DATETIME | 完成时间 |

---

### 2.5 财报披露日历表 `reporting_calendar`

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | INTEGER | 主键，自增 |
| fiscal_year | INTEGER | 会计年度 |
| report_type | VARCHAR(20) | 报表类型 |
| deadline_date | DATE | 监管披露截止日 |
| expected_start | DATE | 预计数据开始出现的时间 |
| is_released | BOOLEAN | 该披露窗口是否已过 |

**A 股财报披露日历参考**：

| 报表 | 截止日 | ETL 建议执行时间 |
|------|--------|------------------|
| 年报 (annual) | 4月30日 | 5月7日 ~ 5月15日 |
| 一季报 (q1) | 4月30日 | 5月7日 ~ 5月15日（可与年报合并） |
| 半年报 (semi_annual) | 8月31日 | 9月7日 ~ 9月15日 |
| 三季报 (q3) | 10月31日 | 11月7日 ~ 11月15日 |

---

## 3. ETL 数据抓取与清洗

### 3.1 四层防御体系

由于 akshare 底层依赖东方财富等第三方公开接口，存在不稳定性，ETL 模块设计四层防御：

```
请求 → [Layer 1: 限速] → [Layer 2: 重试] → 失败? → [Layer 3: 缓存命中?] → [Layer 4: 备用数据源]
```

| 层级 | 机制 | 实现 |
|------|------|------|
| L1 限速 | 请求间隔 0.5~1.5s 随机抖动 | Token Bucket 装饰器，4次/秒 |
| L2 重试 | 最多 5 次，指数退避 1s~60s | tenacity 库，捕获 ConnectionError/Timeout/空DataFrame |
| L3 缓存 | 历史数据缓存 6 小时，实时数据 30 分钟 | diskcache，key=函数名+参数哈希 |
| L4 备用源 | Eastmoney → Sina 财经 | akshare 内部封装了新浪接口 |

### 3.2 数据源映射

| 数据类型 | 主数据源 (akshare 函数) | 备用数据源 (akshare 函数) |
|----------|------------------------|--------------------------|
| 股票列表 | `stock_info_a_code_name()` | — |
| 资产负债表 | `stock_balance_sheet_by_report_em(symbol)` | `stock_financial_report_sina(symbol, "资产负债表")` |
| 利润表 | `stock_profit_sheet_by_report_em(symbol)` | `stock_financial_report_sina(symbol, "利润表")` |
| 现金流量表 | `stock_cash_flow_sheet_by_report_em(symbol)` | `stock_financial_report_sina(symbol, "现金流量表")` |
| 股票详情 | `stock_individual_info_em(symbol)` | `stock_profile_cninfo(symbol)` |

### 3.3 数据清洗流程（Cleaner）

1. **单位统一**：东方财富返回的数据单位是**元**，但如果改用新浪备用源，数据可能是**万元**。清洗时需检测数量级（如 total_assets > 1e12 则很可能单位是万元），统一转为**元**存储。

2. **列名映射**：akshare 返回的 DataFrame 列名为中文（如 "总资产"、"营业总收入"），需要映射为数据库英文字段名。该映射维护在 `app/services/etl/column_mapping.py`。

3. **空值处理**：pandas NaN → Python None → SQL NULL。注意区分"数值为 0"和"未披露"的语义差异。

4. **报表类型推断**：根据 report_date 的月和日推断：
   - `MM-DD = 12-31` → annual
   - `MM-DD = 06-30` → semi_annual
   - `MM-DD = 03-31` → q1
   - `MM-DD = 09-30` → q3

5. **累积值转单季度值**：
   - 利润表和现金流量表的 YTD 累积值需要减去同一财年内前一个报表期的累积值
   - 例：Q3 单季度营收 = Q3 累积营收 − 半年报累积营收
   - 年报数据无需转换（本身就是全年值）
   - 单季度值存入 `financial_indicators` 表，不修改原始累积数据

6. **数据校验**：
   - DataFrame 非空（len > 0）
   - 关键字段存在：report_date, total_assets, operating_revenue, net_profit
   - total_assets > 0（基本合理性）
   - |total_assets − (total_liabilities + total_equity)| / total_assets < 1%（会计恒等式校验）

### 3.4 ETL 执行流程

#### 全量同步 `full_sync`

```
1. 创建 sync_log 记录 (status='running')
2. 调用 akshare 获取全 A 股列表（~5000 只）
3. 将股票元数据 upsert 到 stocks 表
4. 逐只股票循环（受限速控制）：
   a. 获取最近 N 年（默认 5 年）的三张报表
   b. 清洗数据（列名映射、单位转换、空值处理）
   c. [年报数据] → upsert 到 financial_statements
   d. [年报数据] → 计算并 upsert 到 financial_indicators
   e. [非年报数据] → 检查是否已存在同财年的前置报表数据
      - 若 Q3 且半年报已入库 → 计算单季度值 → upsert
      - 若 Q1 且年报已入库 → 计算单季度值 → upsert
5. 更新 sync_log (status='success'/'partial'/'failed')
```

> 注：版本 v2.0 优先抓取**年报数据**，季报/半年报的累积转单季度逻辑在后续版本完善。

#### 增量同步 `incremental_sync`

```
1. 查询 DB 中每只股票的 MAX(report_date)
2. 批量对比 akshare 最新可用报表期
3. 仅对有新报表的股票执行抓取
4. 新报表按上述流程清洗入库
```

---

## 4. 核心 API 路由定义

### 4.1 API 总览

| 接口 | 方法 | 功能 | 优先级 |
|------|------|------|--------|
| `/` 或 `/api/v1/health` | GET | 健康检查 | P0 |
| `/api/v1/stocks` | GET | 股票列表（分页 + 搜索 + 行业筛选） | P0 |
| `/api/v1/stocks/{symbol}` | GET | 单只股票详情 + 最新财务摘要 | P0 |
| `/api/v1/stocks/{symbol}/financials` | GET | 单只股票完整财务历史 | P0 |
| `/api/v1/indicators` | GET | 可筛选指标列表及其中文说明 | P1 |
| `/api/v1/data/sync` | POST | 触发数据同步 | P1 |
| `/api/v1/data/sync/status` | GET | 查询同步状态 | P1 |
| `/api/v1/screener/search` | POST | 多条件选股筛选 | P2 |
| `/api/v1/valuation/dcf` | POST | DCF 估值计算 | P2 |
| `/api/v1/valuation/ddm` | POST | DDM 估值计算 | P2 |
| `/api/v1/auth/wechat-login` | POST | 微信登录 | P2 |

> **本次开发（v2.0）聚焦 P0 优先级**，先实现数据抓取和基础查询功能。

---

### 4.2 模块 A：股票与财务数据查询

#### `GET /api/v1/stocks`

**功能**：分页获取股票列表，支持关键词搜索和行业筛选。

**请求参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| keyword | string | 否 | — | 按股票代码或名称模糊搜索 |
| industry | string | 否 | — | 按申万一级行业精确筛选 |
| page | int | 否 | 1 | 页码 |
| page_size | int | 否 | 20 | 每页数量（最大 100） |

**响应示例**：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "symbol": "600519",
        "name": "贵州茅台",
        "market": "SH",
        "industry": "食品饮料",
        "list_date": "2001-08-27",
        "total_shares": 1256197800
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

---

#### `GET /api/v1/stocks/{symbol}`

**功能**：获取单只股票基本信息和最新一期的核心财务指标。

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| symbol | string | 股票代码 |

**响应示例**：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "symbol": "600519",
    "name": "贵州茅台",
    "market": "SH",
    "industry": "食品饮料",
    "total_shares": 1256197800,
    "latest_financial": {
      "report_date": "2024-12-31",
      "report_type": "annual",
      "operating_revenue": 174120000000.00,
      "net_profit_attr_parent": 85920000000.00,
      "total_assets": 298750000000.00,
      "total_equity": 237620000000.00,
      "basic_eps": 68.40,
      "roe": 0.3618,
      "gross_margin": 0.9240,
      "net_margin": 0.4934,
      "revenue_yoy": 0.1485,
      "net_profit_yoy": 0.1484,
      "debt_to_assets": 0.2045,
      "fcf": 68500000000.00
    }
  }
}
```

---

#### `GET /api/v1/stocks/{symbol}/financials`

**功能**：获取单只股票的全部财务历史。

**请求参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| report_type | string | 否 | — | 筛选报表类型：'annual'/'semi_annual'/'q1'/'q3'。不传则返回全部 |
| years | int | 否 | 5 | 返回最近 N 年的数据 |

**响应示例**：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "symbol": "600519",
    "financials": [
      {
        "report_date": "2024-12-31",
        "report_type": "annual",
        "fiscal_year": 2024,
        "operating_revenue": 174120000000.00,
        "net_profit_attr_parent": 85920000000.00,
        "total_assets": 298750000000.00,
        "...": "...(全部 financial_statements + financial_indicators 字段)"
      },
      {
        "report_date": "2023-12-31",
        "report_type": "annual",
        "fiscal_year": 2023,
        "...": "..."
      }
    ]
  }
}
```

---

#### `GET /api/v1/indicators`

**功能**：返回所有可用于筛选的指标列表，供前端构建筛选 UI。

**响应示例**：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "indicators": [
      {
        "field": "operating_revenue",
        "chinese_name": "营业总收入",
        "unit": "元",
        "category": "利润表",
        "is_ratio": false
      },
      {
        "field": "net_profit_attr_parent",
        "chinese_name": "归母净利润",
        "unit": "元",
        "category": "利润表",
        "is_ratio": false
      },
      {
        "field": "roe",
        "chinese_name": "净资产收益率(ROE)",
        "unit": "%",
        "category": "盈利能力",
        "is_ratio": true
      },
      {
        "field": "gross_margin",
        "chinese_name": "毛利率",
        "unit": "%",
        "category": "盈利能力",
        "is_ratio": true
      },
      {
        "field": "revenue_yoy",
        "chinese_name": "营收同比增长率",
        "unit": "%",
        "category": "成长能力",
        "is_ratio": true
      },
      {
        "field": "debt_to_assets",
        "chinese_name": "资产负债率",
        "unit": "%",
        "category": "偿债能力",
        "is_ratio": true
      }
    ]
  }
}
```

---

### 4.3 模块 B：数据同步

#### `POST /api/v1/data/sync`

**功能**：手动触发 ETL 数据同步。

**请求体**：

```json
{
  "sync_type": "full_sync",
  "years": 5,
  "symbols": ["600519"],
  "report_types": ["annual"]
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sync_type | string | 否 | 'full_sync'(默认) / 'incremental_sync' |
| years | int | 否 | 抓取最近几年，默认 5 |
| symbols | string[] | 否 | 指定股票代码列表，不传则全量 |
| report_types | string[] | 否 | 指定报表类型，不传则全部 |

**响应**：

```json
{
  "code": 200,
  "message": "全量同步任务已启动",
  "data": {"job_id": 42}
}
```

---

#### `GET /api/v1/data/sync/status`

**功能**：查询最近同步任务的状态。

**响应**：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "latest_jobs": [
      {
        "id": 42,
        "job_type": "full_sync",
        "status": "success",
        "stocks_total": 5000,
        "stocks_synced": 4980,
        "stocks_failed": 20,
        "reports_fetched": 24900,
        "started_at": "2026-05-08T02:00:00",
        "completed_at": "2026-05-08T05:30:00"
      }
    ]
  }
}
```

---

## 5. 筛选引擎设计

> 注：筛选引擎属于 P2 优先级，v2.0 版本仅完成设计，后续实现。

### 5.1 接口定义

**`POST /api/v1/screener/search`**

**请求体设计**：

```json
{
  "conditions": [
    {
      "expression": "net_profit_attr_parent / total_assets > 0.15",
      "report_type": "annual",
      "consecutive_years": 3
    },
    {
      "expression": "revenue_yoy > 0.10 AND net_profit_yoy > 0.10",
      "report_type": "annual",
      "consecutive_years": 2
    },
    {
      "expression": "debt_to_assets < 0.60",
      "report_type": "annual",
      "consecutive_years": 1
    }
  ],
  "industry_filter": ["食品饮料", "医药生物"],
  "page": 1,
  "page_size": 20
}
```

### 5.2 表达式语法

支持的操作：

| 类别 | 支持内容 | 示例 |
|------|----------|------|
| 算术运算 | `+` `-` `*` `/` `( )` | `(revenue - cost) / revenue` |
| 比较运算 | `>` `<` `>=` `<=` `==` `!=` | `roe > 0.15` |
| 逻辑运算 | `AND` `OR` | `roe > 0.15 AND debt_to_assets < 0.6` |
| 函数 | 待定 | `yoy(field)`, `avg(field, 3)` 等 |

### 5.3 连续 N 年逻辑

`consecutive_years` 表示该条件需要在**连续的最近 N 份同类型报表**中均满足。
- 如 `consecutive_years: 3` 且 `report_type: annual`，则需检查最近 3 份年报
- 实现方式：按 fiscal_year 降序取前 N 条，检查是否连续且全部满足条件

---

## 6. 估值模型设计

> 注：估值模型属于 P2 优先级，v2.0 版本仅完成设计，后续实现。

### 6.1 DCF 自由现金流折现模型

**接口**：`POST /api/v1/valuation/dcf`

**数学公式（两阶段模型）**：

```
阶段一（可明确预测期 t = 1, 2, ..., n）：
  PV_stage1 = Σ FCF_base × (1 + g1)^t / (1 + WACC)^t

终值（永续增长）：
  Terminal Value = FCF_base × (1 + g1)^n × (1 + g2) / (WACC - g2)
  PV_terminal = Terminal Value / (1 + WACC)^n

企业价值 = PV_stage1 + PV_terminal
股权价值 = 企业价值 - 净负债
每股内在价值 = 股权价值 / 总股本
```

**请求体**：

```json
{
  "symbol": "600519",
  "fcf_base": null,
  "forecast_years": 5,
  "growth_rate_stage1": 0.10,
  "growth_rate_terminal": 0.03,
  "wacc": 0.08,
  "net_debt": null,
  "total_shares": null
}
```

**参数自动填充规则**（当传入 `null` 时）：

| 参数 | 自动填充来源 |
|------|-------------|
| fcf_base | `financial_indicators` 最新一条的 `fcf` 字段（经营现金流 − 资本支出） |
| net_debt | 最新 `short_term_borrowings + long_term_borrowings − cash_and_equivalents` |
| total_shares | `stocks.total_shares` |

**响应**（包含输入参数和计算结果，方便用户审视假设）：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "input_params": {
      "fcf_base": 68500000000,
      "fcf_base_source": "auto_filled",
      "forecast_years": 5,
      "growth_rate_stage1": 0.10,
      "growth_rate_terminal": 0.03,
      "wacc": 0.08,
      "net_debt": -45800000000,
      "net_debt_source": "auto_filled",
      "total_shares": 1256197800,
      "total_shares_source": "auto_filled"
    },
    "result": {
      "enterprise_value": 1750000000000.00,
      "equity_value": 1795800000000.00,
      "fair_value_per_share": 1429.68,
      "pv_stage1": 271800000000.00,
      "pv_terminal": 1478200000000.00
    }
  }
}
```

---

### 6.2 DDM 股利折现模型

**接口**：`POST /api/v1/valuation/ddm`

**数学公式（两阶段模型）**：

```
阶段一：
  PV_stage1 = Σ D0 × (1 + g1)^t / (1 + r)^t   (t = 1, 2, ..., n)

终值：
  Terminal Value = D0 × (1 + g1)^n × (1 + g2) / (r - g2)
  PV_terminal = Terminal Value / (1 + r)^n

每股内在价值 = PV_stage1 + PV_terminal
```

**请求体**：

```json
{
  "symbol": "600519",
  "d0": null,
  "forecast_years": 5,
  "growth_rate_stage1": 0.08,
  "growth_rate_terminal": 0.02,
  "required_return": 0.07
}
```

**自动填充规则**：

| 参数 | 自动填充来源 |
|------|-------------|
| d0 | `financial_indicators` 最新一条的 `dividend_per_share` |

---

## 7. 鉴权方案

> 注：P2 优先级，v2.0 版本先实现无鉴权的公开 API，后续再加微信登录。

### 7.1 微信小程序登录流程

```
小程序端                        后端                        微信服务器
   │                             │                             │
   │── wx.login() ──────────────────────────────────────────→  │
   │←── code ───────────────────────────────────────────────  │
   │                             │                             │
   │── POST /auth/wechat-login ─→│                             │
   │   { code }                  │── GET /sns/jscode2session ─→│
   │                             │   ?appid=xxx&secret=xxx     │
   │                             │   &js_code={code}           │
   │                             │←── { openid, session_key }─ │
   │                             │                             │
   │                             │ 生成 JWT (含 openid)         │
   │←── { token, user_info } ────│                             │
   │                             │                             │
   │── 后续请求 Header: ─────────→│                             │
   │   Authorization: Bearer JWT │ 验证 JWT → 提取 openid       │
```

### 7.2 JWT 设计

- **签发**：登录时由后端生成，有效期 7 天
- **载荷**：`{"openid": "xxx", "exp": timestamp}`
- **验证**：所有需要鉴权的接口通过 FastAPI Dependency 注入验证

---

## 8. 非功能性需求

### 8.1 错误码规范

| HTTP 状态码 | 含义 | 使用场景 |
|-------------|------|----------|
| 200 | 成功 | 正常响应 |
| 400 | 请求参数错误 | 缺少必填字段、参数类型错误 |
| 401 | 未认证 | 缺少或无效 JWT Token |
| 404 | 资源不存在 | 股票代码无效、接口路径错误 |
| 429 | 请求过于频繁 | 触发限流 |
| 500 | 服务器内部错误 | 未知异常 |
| 502 | 上游数据源不可用 | akshare 全部数据源失败 |

### 8.2 限流策略

| 端点类型 | 限制 | 粒度 |
|----------|------|------|
| GET 查询接口 | 100 次/分钟 | 按 IP |
| POST 筛选/估值 | 30 次/分钟 | 按 IP（鉴权后按用户） |
| POST /data/sync | 1 次/小时 | 全局限流 |

### 8.3 性能要求

| 场景 | 目标 |
|------|------|
| 单只股票财务历史查询 | < 200ms |
| 全量股票列表（分页） | < 300ms |
| 全量 ETL 同步（~5000 只 × 5 年） | < 8 小时（限速导致的硬上限） |
| 筛选查询（未来） | < 3s |

---

## 9. 项目目录结构

```
D:\尤里卡\
├── 系统架构与后端 PRD 文档.md       ← 本文档
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI 应用入口、路由注册、异常处理器
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py            # 配置管理 (pydantic-settings)
│   │   │   ├── database.py          # SQLAlchemy engine, SessionLocal
│   │   │   └── exceptions.py        # 自定义异常类
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── stocks.py            # Stock ORM 模型
│   │   │   ├── financials.py        # FinancialStatement ORM 模型（核心）
│   │   │   ├── indicators.py        # FinancialIndicator ORM 模型
│   │   │   └── sync.py              # SyncLog ORM 模型
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── stocks.py            # 股票相关 Pydantic 模型
│   │   │   ├── financials.py        # 财务数据 Pydantic 模型
│   │   │   ├── screener.py          # 筛选请求/响应模型
│   │   │   ├── valuation.py         # 估值请求/响应模型
│   │   │   └── common.py            # APIResponse, PaginatedData 通用包装
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── etl/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── fetcher.py       # akshare 数据抓取（四层防御）
│   │   │   │   ├── cleaner.py       # 数据清洗、列映射、单位转换
│   │   │   │   ├── loader.py        # 数据入库（upsert + 指标计算）
│   │   │   │   ├── scheduler.py     # ETL 编排（全量/增量同步）
│   │   │   │   └── column_mapping.py # akshare 中文列名 → 数据库英文字段名
│   │   │   ├── screener.py          # 筛选表达式引擎（后续）
│   │   │   └── valuation.py         # DCF/DDM 估值计算（后续）
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── stocks.py            # /api/v1/stocks 路由
│   │   │   ├── financials.py        # /api/v1/stocks/{symbol}/financials 路由
│   │   │   ├── data.py              # /api/v1/data/sync 路由
│   │   │   ├── screener.py          # /api/v1/screener 路由（后续）
│   │   │   └── valuation.py         # /api/v1/valuation 路由（后续）
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── rate_limit.py        # IP 限流中间件
│   │       └── pagination.py        # 分页工具函数
│   ├── data/                        # SQLite 数据库文件 + diskcache（gitignore）
│   │   └── .gitkeep
│   └── scripts/
│       ├── init_db.py               # 数据库初始化 + 创建表
│       └── run_etl.py               # ETL 手动触发脚本
```

---

## 10. 数据更新策略

### 10.1 定期同步计划

| 时间 | 操作 | 说明 |
|------|------|------|
| 5月7日~15日 | 全量同步 | 年报 + 一季报数据已基本披露完毕 |
| 9月7日~15日 | 增量同步 | 半年报数据基本披露完毕 |
| 11月7日~15日 | 增量同步 | 三季报数据基本披露完毕 |
| 每周日凌晨 | 轻量刷新 | 更新股票元数据（名称变更、行业重分类、新上市/退市） |

### 10.2 手动触发

管理后台或 API 调用 `POST /api/v1/data/sync` 可随时触发同步。支持：
- 指定股票代码列表（单只或批量）
- 指定抓取年数
- 指定报表类型

---

> **文档版本 v2.0 | 2026-07-26 | 待审核**
