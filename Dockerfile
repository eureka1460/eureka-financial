FROM python:3.12-slim

WORKDIR /app

# 系统库（aksale 依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libxml2-dev libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY backend/ .

# 启动
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
