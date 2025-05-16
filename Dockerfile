FROM python:3.9-slim

WORKDIR /app

# 複製必要檔案
COPY . /app/
COPY requirements.txt .

# 安裝相依套件
RUN pip install --no-cache-dir -r requirements.txt

# 端口設定
EXPOSE 5000

# 啟動 API 服務
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
