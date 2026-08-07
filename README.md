# Eureka 财报研究

A 股上市公司财报查询、财务分析与估值计算微信小程序。

---

## 一、项目概览

一个完整的全栈微信小程序，覆盖 A 股 5000+ 上市公司真实财报数据，提供多期财务报表对比、自定义条件选股、DCF/DDM 估值模型等核心功能。

### 核心功能

| 功能 | 说明 |
|------|------|
| 股票搜索 | 按代码/名称搜索，行业筛选，分页列表 |
| 多期财报对比 | 横滑对比表，年报/季报累计值展示，近1年/3年/5年切换 |
| 财务指标图表 | 点击任意指标弹出柱状图，年报/季报切换，同比标签 |
| 条件选股 | 多指标组合筛选，AND/OR 逻辑，连续 N 年条件 |
| DCF 估值 | 两阶段自由现金流折现，WACC 自动计算并支持明细编辑 |
| DDM 估值 | 两阶段股利折现，股利自动填充（财报/估算） |
| 指标帮助 | 每个财务指标旁有问号按钮，点击弹出会计定义 |

---

## 二、系统架构

```
┌─ 微信小程序 (miniprogram/)
│  ├─ 4 个页面: 首页/个股详情/选股筛选/估值计算
│  ├─ 3 个组件: 柱状图/筛选条件/指标帮助
│  └─ 通过云函数调用后端 API
│
├─ 云函数 (cloudfunctions/apiProxy/)
│  └─ Node.js 原生 HTTPS 代理，转发请求到云托管后端
│
├─ Python 后端 (backend/)
│  ├─ FastAPI + SQLAlchemy
│  ├─ 9 个 API 接口（股票/财务/筛选/估值/同步）
│  └─ ETL 数据抓取流水线
│
├─ 数据库
│  └─ MySQL 8.0（微信云开发托管，数据永久保存）
│
└─ 部署
   └─ 微信云托管（Docker 容器，Git Push 自动部署）
```

### 数据流

```
东方财富 API ──▶ akshare 封装 ──▶ Fetcher（四层防御）
                                    │
                                    ▼
                              Cleaner（六步清洗）
                                    │
                                    ▼
                              Loader（upsert 入库）
                                    │
                          ┌─────────┴──────────┐
                          ▼                    ▼
                   financial_statements   financial_indicators
                   (77 列财报宽表)       (同花顺预计算指标)
                          │                    │
                          └────────┬───────────┘
                                   ▼
                            FastAPI REST API
                                   │
                                   ▼
                            微信小程序前端
```

---

## 三、数据抓取与处理

### 3.1 数据源

| 数据类型 | 数据源 | 接口/库 |
|----------|--------|---------|
| 资产负债表 | 东方财富 | `akshare.stock_balance_sheet_by_report_em()` |
| 利润表（单季度） | 东方财富 | `akshare.stock_profit_sheet_by_quarterly_em()` |
| 现金流量表（单季度） | 东方财富 | `akshare.stock_cash_flow_sheet_by_quarterly_em()` |
| 计算指标 | 同花顺 | `akshare.stock_financial_abstract_ths()` |
| 股票列表 | 东方财富 | `akshare.stock_info_a_code_name()` |
| 行业分类 | 东方财富 | `akshare.stock_board_industry_name_em()` |

### 3.2 ETL 流水线（四层防御）

```
L1：限速器（Token Bucket）
  └─ 调用间隔 0.5-1.5s 随机抖动，避免触发反爬

L2：重试机制（指数退避）
  └─ 失败后 1s → 2s → 4s → 8s → 16s，最多5次

L3：磁盘缓存（diskcache）
  └─ 历史数据缓存 6 小时，元数据缓存 30 分钟

L4：备用数据源
  └─ 东方财富失败 → 新浪财经
```

### 3.3 清洗流水线（六步）

1. **列名映射**：aksale 英文缩写 → 数据库英文字段名（80+ 条映射）
2. **单位检测**：中位数法判断万元/元，自动 ×10000 转换
3. **空值处理**：pandas NaN → Python None → SQL NULL
4. **日期推断**：从 `YYYY-MM-DD` 推断 `report_type`（q1/semi_annual/q3/annual）
5. **元数据注入**：symbol, data_source, currency
6. **数据校验**：总资产 > 0，|资产 − 负债 − 权益| / 总资产 < 1%

### 3.4 指标数据策略

**关键设计决策：指标从同花顺直接获取，不自行计算。**

同花顺 `stock_financial_abstract_ths()` 返回 74 期预计算指标（覆盖 2007 至今所有季度），包括：
ROE、ROA、毛利率、净利率、营业利润率、YoY 增长率、流动比率、速动比率、保守速动比率、资产负债率、权益乘数、存货周转率、应收账款周转率、总资产周转率、每股净资产、每股收益、每股经营现金流等。

唯一自行计算的指标：**FCF = 经营现金流净额 + 投资活动现金流净额**。

### 3.5 数据同步模式

| 模式 | API 参数 | 说明 |
|------|---------|------|
| 全量分批 | `{"sync_type":"batch_sync","years":5,"batch_size":50}` | 拉取全部 5000+ 只股票，每批 50 只，支持断点续传 |
| 指定股票 | `{"sync_type":"full_sync","symbols":["000333"]}` | 开发测试用 |
| 季度增量 | `{"sync_type":"incremental_sync"}` | 财报披露后增量更新，只拉有新报表的股票 |

---

## 四、估值模型

### 4.1 DCF 两阶段自由现金流折现

```
企业价值 = Σ(FCF_t / (1+WACC)^t) + 终值/(1+WACC)^n
每股价值 = (企业价值 − 净负债) / 总股本
```

**阶段一**（可明确预测期，默认 5 年）：逐年折现 FCF × (1+g1)^t

**阶段二**（永续期）：终值 = FCF_terminal / (WACC − g2)，使用戈登增长模型

**参数自动填充：**
| 参数 | 自动填充方式 |
|------|-------------|
| FCF 基期 | 最近一年年报 FCF |
| 净负债 | 短期借款 + 长期借款 − 货币资金 |
| 总股本 | 从 stocks 表读取，失败则 EPS 反推 |
| WACC | 自动计算（详见下方） |

### 4.2 WACC 自动计算

```
WACC = E/(E+D) × (Rf + β × RP) + D/(E+D) × Kd × (1 − T)

其中：
  - E = 股东权益，D = 总负债
  - Rf = 2.5%（十年期国债）
  - β = 行业参考值（15 个行业，0.7-1.3）
  - RP = 5.5%（市场风险溢价）
  - Kd = 利息费用 / 有息负债
  - T = 所得税 / 利润总额
```

全部计算明细可在小程序估值页展开 WACC 面板查看和编辑。

### 4.3 DDM 两阶段股利折现

```
每股价值 = Σ(D_t / (1+r)^t) + 终值/(1+r)^n
```

股利自动填充：优先取财报真实数据，取不到则 EPS × 30% 估算，来源明确标注。

---

## 五、筛选引擎

### 5.1 架构

```
用户条件 JSON ──▶ 条件解析器 ──▶ SQL 编译 ──▶ 数据库查询 ──▶ AND/OR 集合运算
```

### 5.2 支持的条件类型

| 类型 | 示例 | 说明 |
|------|------|------|
| 单指标 | `roe >= 0.15` | 直接字段比较 |
| 多指标表达式 | `(ocf − capex) / revenue` | 先在 Python 中计算，再比较 |
| 连续 N 年 | `roe >= 0.15 连续3年` | 最近 N 份同类报表全部满足 |
| 逻辑组合 | AND / OR | 多条件集合运算 |

### 5.3 实现细节

- **指标分表查询**：FinancialIndicator 字段查 indicator 表，FinancialStatement 字段查 statement 表
- **连续 N 年**：窗口函数 `ROW_NUMBER() OVER PARTITION BY symbol ORDER BY date DESC`，取前 N 条检查是否全满足
- **表达式计算**：查原始数据后在 Python 中 `eval()` 计算（禁 builtins 防注入）
- **行业筛选**：先缩小候选集，再组合条件

---

## 六、数据库设计

4 张核心表，132 个字段：

| 表名 | 字段数 | 说明 |
|------|--------|------|
| `stocks` | 10 | 股票基本信息（代码、名称、行业、股本） |
| `financial_statements` | 77 | 财报宽表（资产负债表 + 利润表 + 现金流量表） |
| `financial_indicators` | 29 | 计算指标（盈利能力/成长/偿债/营运/估值） |
| `sync_log` | 10 | ETL 同步审计日志 |

### 宽表设计（financial_statements）

每行 = 一只股票的一个报表期的完整财报，唯一约束 `(symbol, report_date, report_type)`。

字段分组：
- 资产负债表：资产 (16)、负债 (12)、权益 (6)
- 利润表：收入、费用、利润 (21)
- 现金流量表：经营/投资/筹资 (12)

---

## 七、技术栈

| 层级 | 技术 |
|------|------|
| 前端 | 微信原生小程序 (WXML/WXSS/JS) |
| 云函数 | Node.js (原生 HTTPS 模块) |
| 后端框架 | FastAPI (Python 3.12) |
| ORM | SQLAlchemy 2.x |
| 数据库 | MySQL 8.0 (云开发托管) / SQLite (本地开发) |
| 数据抓取 | akshare + pandas + numpy |
| 缓存 | diskcache |
| 重试 | tenacity (指数退避) |
| 部署 | 微信云托管 (Docker) + GitHub Actions |

---

## 八、部署架构

```
小程序 ──▶ apiProxy 云函数 ──▶ 云托管 FastAPI ──▶ MySQL

GitHub Push ──▶ 云托管自动拉取构建 ──▶ 新版上线
```

- **数据库**：MySQL 8.0，数据永久保存，不受容器重启影响
- **后端自动扩容**：0 请求时休眠（可关），有请求时自动唤醒
- **前端发布**：微信审核 → 灰度 → 全量

---

## 九、目录结构

```
eureka投研/
├── backend/                    Python 后端
│   ├── app/
│   │   ├── main.py             启动入口（异常处理 + 路由注册 + 启动种子数据）
│   │   ├── core/               基础设施（配置/数据库/异常类）
│   │   ├── models/             ORM 模型（4 表）
│   │   ├── schemas/            Pydantic 请求/响应模型
│   │   ├── services/           业务逻辑
│   │   │   ├── etl/            数据抓取/清洗/入库/编排
│   │   │   ├── screener.py     选股筛选引擎
│   │   │   └── valuation.py    DCF/DDM 估值引擎
│   │   └── routers/            9 个 API 路由
│   ├── scripts/                init_db / run_etl
│   ├── requirements.txt
│   └── data/                   本地开发数据库
│
├── miniprogram/                微信小程序前端
│   ├── app.js                  云环境初始化
│   ├── app.wxss                CSS 设计系统（变量/卡片/标签/按钮）
│   ├── utils/                   API 封装 / 格式化工具
│   ├── components/             柱状图 / 筛选条件 / 指标帮助
│   └── pages/                  4 个页面
│       ├── index/              首页（搜索+列表）
│       ├── stock/              个股详情（对比表+图表）
│       ├── screener/           选股筛选
│       └── valuation/          估值计算
│
├── cloudfunctions/apiProxy/    API 代理云函数
├── Dockerfile                  云托管构建
└── README.md                   本文档
```

---

## 十、免责声明

本工具所有财务数据和计算结果来源于公开财报接口，仅供参考，**不构成任何投资建议**。投资有风险，入市需谨慎。
