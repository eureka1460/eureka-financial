# Eureka 财报研究

A 股财报选股与估值分析小程序。

## 功能

- 🔍 **股票搜索**：按代码、名称搜索 A 股，按行业筛选
- 📊 **财报分析**：查看完整财务报表 + 计算指标（ROE、毛利率、增长率等）
- 🎯 **条件选股**：多条件组合筛选（连续 N 年逻辑、AND/OR 组合）
- 💰 **估值模型**：DCF 自由现金流折现 + DDM 股利折现，支持自动参数填充

## 项目结构

```
├── backend/               Python FastAPI 后端
│   ├── app/               API 路由 / 模型 / 业务逻辑 / ETL
│   ├── scripts/           数据库初始化 & 数据抓取
│   └── data/              运行时数据库 & 缓存
├── miniprogram/           微信小程序前端
│   ├── pages/             4 个页面（首页/详情/筛选/估值）
│   ├── components/        3 个复用组件
│   └── utils/             API 封装 & 格式化工具
├── cloudfunctions/        微信云函数
│   └── apiProxy/          API 代理（小程序 → 后端）
└── docs/                  架构文档 & PRD
```

## 快速开始

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
python scripts/init_db.py --seed
uvicorn app.main:app --reload --port 8000
```

### 2. 云函数

在微信开发者工具中，右键 `cloudfunctions/apiProxy/` → 上传并部署。

部署前记得修改 `config.json` 中的 `BACKEND_URL` 为你的后端地址。

### 3. 小程序

微信开发者工具打开项目根目录，编译预览即可。

## 技术栈

- **后端**: FastAPI + SQLAlchemy + SQLite + akshare + pandas
- **前端**: 微信原生小程序 + 云函数
- **部署**: 后端 Render / 服务器，前端微信审核发布
