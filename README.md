# Eureka 财报研究

A 股财报选股与估值分析小程序。

## 功能

- 🔍 **股票搜索**：按代码、名称搜索 A 股，按行业筛选
- 📊 **财报分析**：多期数据对比表 + 历年年报/季报柱状图（含同比增长率）
- 🎯 **条件选股**：多条件组合筛选（AND/OR 逻辑 + 连续 N 年）
- 💰 **估值模型**：DCF 自由现金流折现 + DDM 股利折现，WACC 支持详细分解编辑

## 数据源

- **原始财报**：东方财富 `_by_report_em` 接口（资产负债表/利润表/现金流量表）
- **计算指标**：同花顺预计算接口（ROE/ROA/毛利率/速动比率/周转率等，覆盖所有季度）
- **FCF**：经营现金流净额 + 投资活动现金流净额

## 项目结构

```
├── backend/               Python FastAPI 后端
│   ├── app/               API 路由 / 模型 / 业务逻辑 / ETL
│   ├── scripts/           数据库初始化 & 数据抓取
│   └── data/              运行时数据 & 缓存
├── miniprogram/           微信小程序前端
│   ├── pages/             4 个页面（首页/个股/筛选/估值）
│   ├── components/        柱状图 / 筛选条件 / 指标帮助
│   └── utils/             API 封装 & 格式化工具
├── cloudfunctions/        微信云函数
│   └── apiProxy/          API 代理（小程序 → 后端）
└── Dockerfile             云托管部署
```

## 部署架构

```
小程序 ──▶ 云函数 apiProxy ──▶ 云托管 FastAPI ──▶ MySQL（云开发托管数据库）
```

- 后端：微信云托管，Git Push 自动部署
- 数据库：MySQL 8.0，数据永久保存
- 代理：微信云函数，只做请求转发

## 数据同步

| 模式 | 用法 | 说明 |
|------|------|------|
| 全量分批 | `POST /api/v1/data/sync {"sync_type":"batch_sync","years":5,"batch_size":50}` | 5000 只 A 股分批 |
| 指定股票 | `POST /api/v1/data/sync {"sync_type":"full_sync","symbols":["000333"]}` | 测试用 |
| 季度增量 | `POST /api/v1/data/sync {"sync_type":"incremental_sync"}` | 季度更新 |

支持断点续传：传入 `"start_from": 2500` 从中间继续。

## 技术栈

- **后端**: FastAPI + SQLAlchemy + PyMySQL + akshare + pandas
- **数据库**: MySQL 8.0（云开发托管）/ SQLite（本地开发）
- **前端**: 微信原生小程序 + 云函数
- **部署**: 微信云托管 + 云开发 MySQL
