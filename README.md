# PTT 爬蟲 API 服務

這是基於 [jwlin/ptt-web-crawler](https://github.com/jwlin/ptt-web-crawler) 專案所開發的 HTTP API 服務，可以用來爬取 PTT 網路版的文章。透過這個服務，您可以使用 HTTP 請求輕鬆地獲取 PTT 文章資料，而不需要自己實作爬蟲邏輯。

## 功能特色

- 支援透過 HTTP API 爬取特定看板的文章
- 支援以頁數範圍或特定文章 ID 進行爬取
- 支援僅爬取文章列表資訊（標題、作者、日期和推噓文數目），不需進入文章內頁
- 提供 JSON 格式的回應，方便程式整合
- Docker 化部署，環境隔離且易於維護

## 安裝與環境設定

### 前置準備

確保您已經 fork 了 [jwlin/ptt-web-crawler](https://github.com/jwlin/ptt-web-crawler) 專案。在該專案的根目錄中，新增本專案中的檔案：

1. app.py (Flask API 應用程式)
2. requirements.txt (合併後的相依套件清單)
3. Dockerfile (容器化設定檔)
4. 這個 README.md (更新指南)

## 安裝與執行

### 本地開發環境

1. 安裝所需的 Python 套件：

```bash
pip install -r requirements.txt
```

2. 執行 API 服務：

```bash
python app.py
```

服務將在 http://localhost:5000 啟動

### 使用 Docker 部署

1. 建構 Docker 映像檔：

```bash
docker build -t ptt-crawler-api .
```

2. 執行 Docker 容器：

```bash
docker run -p 5000:5000 ptt-crawler-api
```

## API 使用說明

### 爬取特定看板文章 (依頁數範圍)

```
GET /api/articles?board={看板名稱}&start={起始頁}&end={結束頁}
```

參數說明：
- `board`: PTT 看板名稱，例如 Gossiping、Baseball 等
- `start`: 起始頁數
- `end`: 結束頁數

範例：
```
GET /api/articles?board=Gossiping&start=1&end=5
```

### 爬取特定文章

```
GET /api/article/{文章ID}?board={看板名稱}
```

參數說明：
- `article_id`: 文章的 ID
- `board`: PTT 看板名稱

範例：
```
GET /api/article/M.1234567890.A.123?board=Gossiping
```

### 爬取特定看板文章列表資訊 (不含文章內容)

```
GET /api/articles/list?board={看板名稱}&start={起始頁}&end={結束頁}
```

參數說明：
- `board`: PTT 看板名稱，例如 Gossiping、Baseball 等
- `start`: 起始頁數
- `end`: 結束頁數

範例：
```
GET /api/articles/list?board=Gossiping&start=1&end=5
```

此 API 將只回傳文章列表資訊（標題、作者、日期和推噓文數目），不包含文章內容，可大幅減少爬取時間。

### 關鍵字搜尋（預留功能）

```
GET /api/search?board={看板名稱}&keyword={關鍵字}
```

參數說明：
- `board`: PTT 看板名稱
- `keyword`: 搜尋關鍵字

## 命令行使用說明

除了 API 服務外，您也可以直接使用命令行來爬取資料：

### 爬取特定看板的特定頁數範圍

```bash
python -m PttWebCrawler -b 看板名稱 -i 起始頁數 結束頁數
```

範例：爬取 Gossiping 板第 1 到第 5 頁的文章
```bash
python -m PttWebCrawler -b Gossiping -i 1 5
```

### 爬取特定文章

```bash
python -m PttWebCrawler -b 看板名稱 -a 文章ID
```

範例：爬取 Gossiping 板上特定 ID 的文章
```bash
python -m PttWebCrawler -b Gossiping -a M.1234567890.A.123
```

### 只爬取文章列表資訊（不含文章內容）

```bash
python -m PttWebCrawler -b 看板名稱 -i 起始頁數 結束頁數 -l
```

範例：只爬取 Gossiping 板第 1 到第 5 頁的文章列表資訊
```bash
python -m PttWebCrawler -b Gossiping -i 1 5 -l
```

使用 `-l` 或 `--list` 參數可以只爬取文章列表資訊（標題、作者、日期和推噓文數目），不會進入每篇文章爬取內容，可大幅減少爬取時間。

## 注意事項

- 請尊重 PTT 網站的使用規則，避免過於頻繁的請求
- 本服務僅供學習與研究使用，請勿用於非法或侵權行為
- 爬取大量頁面可能需要較長時間處理，請耐心等待

## 部署選項

除了本地部署外，您也可以將此服務部署到雲端平台：

1. **Heroku**：適合小型應用，免費方案有限制
2. **AWS Elastic Beanstalk**：適合有一定流量的應用
3. **Google Cloud Run**：適合需要自動擴展的應用
4. **Azure App Service**：微軟雲端平台的應用服務

## 貢獻

歡迎提交 Issue 或 Pull Request 來改進這個專案！
