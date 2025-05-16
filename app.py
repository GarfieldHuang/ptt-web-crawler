from flask import Flask, request, jsonify
import json
import sys
import os
import logging
import traceback

# 設置基本日誌配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 確保可以匯入 PttWebCrawler 模組
# 在實際使用時，您已經 fork 了該專案，這個模組應該已經在您的環境中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PttWebCrawler.crawler import PttWebCrawler
from PttWebCrawler.error_handlers import get_error_response

# 檢測是否在 Azure 環境中運行
IS_AZURE = 'AZURE_FUNCTIONS_ENVIRONMENT' in os.environ or 'WEBSITE_SITE_NAME' in os.environ

# 如果在 Azure 中運行，進行特殊設定
if IS_AZURE:
    logging.info("在 Azure 環境中運行 app.py，進行特殊配置")
    
    try:
        # 導入 Azure 輔助函式
        from PttWebCrawler.azure_helpers import setup_for_azure
        setup_for_azure()
    except Exception as e:
        logging.error(f"配置 Azure 環境失敗: {e}")

app = Flask(__name__)

@app.route('/api/articles', methods=['GET'])
def get_articles():
    """爬取特定看板的文章，可用頁數範圍"""
    # 取得請求參數
    board = request.args.get('board', '')
    start_idx = request.args.get('start', '')
    end_idx = request.args.get('end', '')
    
    # 參數檢查
    if not board:
        return jsonify({"error": "必須提供看板名稱 (board)"}), 400
    
    try:
        # 如果提供了起始與結束頁數
        if start_idx and end_idx:
            start_idx = int(start_idx)
            end_idx = int(end_idx)
            
            # 初始化爬蟲
            crawler = PttWebCrawler(as_lib=True)
            articles = crawler.parse_articles(start_idx, end_idx, board)
            return jsonify(articles)
        else:
            return jsonify({"error": "必須提供起始頁 (start) 和結束頁 (end)"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/article/<article_id>', methods=['GET'])
def get_article_by_id(article_id):
    """爬取特定ID的文章"""
    board = request.args.get('board', '')
    
    # 參數檢查
    if not board:
        return jsonify({"error": "必須提供看板名稱 (board)"}), 400
    
    try:
        # 初始化爬蟲
        crawler = PttWebCrawler(as_lib=True)
        article = crawler.parse_article(article_id, board)
        return jsonify(article)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/search', methods=['GET'])
def search_articles():
    """搜尋特定關鍵字的文章"""
    board = request.args.get('board', '')
    keyword = request.args.get('keyword', '')
    
    # 參數檢查
    if not board:
        return jsonify({"error": "必須提供看板名稱 (board)"}), 400
    if not keyword:
        return jsonify({"error": "必須提供關鍵字 (keyword)"}), 400
    
    try:
        # 初始化爬蟲 (這個功能需要確認原專案是否支援關鍵字搜尋)
        crawler = PttWebCrawler(as_lib=True)
        # 若原專案有實現，可以使用
        # articles = crawler.search_articles(keyword, board)
        
        # 若原專案未實現，可以先回傳未實現訊息
        return jsonify({"error": "關鍵字搜尋功能尚未實現"}), 501
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/articles/list', methods=['GET'])
def get_articles_list():
    """爬取特定看板的文章列表資訊（標題、作者、日期、推噓文數），不進入文章頁面爬取內容"""
    # 取得請求參數
    board = request.args.get('board', '')
    start_idx = request.args.get('start', '')
    end_idx = request.args.get('end', '')
    timeout = request.args.get('timeout', '30')  # 增加可選的超時參數，默認 30 秒
    
    # 記錄請求資訊
    app.logger.info(f"收到爬取文章列表請求: board={board}, start={start_idx}, end={end_idx}, timeout={timeout}")
    
    # 參數檢查
    if not board:
        app.logger.warning("缺少必要參數: 看板名稱")
        return jsonify({"error": "必須提供看板名稱 (board)"}), 400
    
    try:
        # 如果提供了起始與結束頁數
        if start_idx and end_idx:
            try:
                start_idx = int(start_idx)
                end_idx = int(end_idx)
                timeout = int(timeout)
            except ValueError:
                app.logger.warning(f"參數格式錯誤: start={start_idx}, end={end_idx}, timeout={timeout}")
                return jsonify({"error": "頁數和超時參數必須為整數"}), 400
            
            # 參數範圍檢查
            if start_idx <= 0 or end_idx <= 0:
                app.logger.warning(f"頁數參數範圍錯誤: start={start_idx}, end={end_idx}")
                return jsonify({"error": "頁數參數必須大於 0"}), 400
            
            if end_idx < start_idx:
                app.logger.warning(f"頁數範圍錯誤: start={start_idx} 大於 end={end_idx}")
                return jsonify({"error": "結束頁數不能小於起始頁數"}), 400
            
            if timeout < 5:
                app.logger.warning(f"超時參數過小: timeout={timeout}")
                timeout = 5  # 確保最小超時時間
            
            app.logger.info(f"開始爬取 {board} 板的文章列表，頁數: {start_idx}-{end_idx}")
            
            # 初始化爬蟲
            crawler = PttWebCrawler(as_lib=True)
            
            # 在 Azure 上執行時可能需要特殊處理
            is_azure = 'AZURE_FUNCTIONS_ENVIRONMENT' in os.environ or 'WEBSITE_SITE_NAME' in os.environ
            if is_azure:
                app.logger.info("檢測到 Azure 環境，啟用特殊處理")
                # Azure 環境下最小超時時間為 60 秒
                timeout = max(timeout, 60)  
                
                # 顯示 Azure 網路配置相關診斷資訊
                try:
                    import socket
                    app.logger.info(f"主機名稱: {socket.gethostname()}")
                    
                    # 嘗試對 PTT 進行 DNS 查詢，測試基本網路連接
                    try:
                        ptt_ip = socket.gethostbyname('www.ptt.cc')
                        app.logger.info(f"PTT DNS 解析結果: {ptt_ip}")
                    except Exception as e:
                        app.logger.warning(f"無法解析 PTT IP: {e}")
                    
                    # 獲取 Azure 環境變數信息
                    azure_vars = {k: v for k, v in os.environ.items() 
                                if k.startswith('AZURE') or k.startswith('WEBSITE') or k.startswith('HTTP_')}
                    app.logger.info(f"Azure 環境變數: {azure_vars}")
                except Exception as e:
                    app.logger.warning(f"獲取網路診斷資訊失敗: {e}")
            
            # 嘗試執行爬蟲操作
            try:
                result = crawler.parse_list_articles(start_idx, end_idx, board, timeout=timeout)
            except Exception as e:
                app.logger.error(f"爬蟲執行時發生異常: {e}")
                app.logger.error(f"異常詳情: {traceback.format_exc()}")
                
                # 使用錯誤處理模組生成詳細的錯誤響應
                error_response = get_error_response(e, {
                    "board": board,
                    "start": start_idx,
                    "end": end_idx,
                    "timeout": timeout
                })
                
                return jsonify(error_response), 500
            
            # 檢查是否爬取到文章和錯誤
            if 'articles' in result:
                article_count = len(result['articles'])
                app.logger.info(f"從 {board} 板爬取到 {article_count} 篇文章")
                
                if article_count == 0:
                    if 'errors' in result and len(result['errors']) > 0:
                        app.logger.error(f"爬取 {board} 板時出錯: {result['errors']}")
                        # 增加診斷資訊
                        result['diagnosis'] = {
                            'runtime_env': {
                                'is_azure': 'AZURE_FUNCTIONS_ENVIRONMENT' in os.environ or 'WEBSITE_SITE_NAME' in os.environ,
                                'python_version': sys.version,
                                'ip_info': 'Azure App Service 無法獲取外部 IP'
                            },
                            'request_info': {
                                'board': board,
                                'start': start_idx,
                                'end': end_idx,
                                'timeout': timeout
                            }
                        }
            
            return jsonify(result)
        else:
            app.logger.warning("缺少必要參數: 起始頁或結束頁")
            return jsonify({"error": "必須提供起始頁 (start) 和結束頁 (end)"}), 400
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        app.logger.error(f"處理請求時出錯: {str(e)}")
        app.logger.error(f"詳細錯誤: {error_details}")
        
        # 增加更詳細的錯誤回報
        return jsonify({
            "error": str(e), 
            "detail": "服務器處理請求時發生錯誤",
            "trace": error_details.split('\n')[-10:] if 'DEBUG' in os.environ else "啟用 DEBUG 環境變數以查看詳細堆疊追蹤"
        }), 500

# 添加簡單的文檔頁面
@app.route('/', methods=['GET'])
def index():
    return """
    <html>
        <head>
            <title>PTT Web Crawler API</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                h1 { color: #333; }
                .endpoint { margin-bottom: 20px; padding: 10px; background-color: #f5f5f5; border-radius: 5px; }
                .method { font-weight: bold; color: #0066cc; }
                .url { font-family: monospace; }
                .params { margin-top: 10px; }
                .param { margin-left: 20px; }
            </style>
        </head>
        <body>
            <h1>PTT Web Crawler API</h1>
            <div class="endpoint">
                <div class="method">GET</div>
                <div class="url">/api/articles?board={board}&start={start_idx}&end={end_idx}</div>
                <div class="params">
                    <div class="param"><strong>board</strong>: PTT 看板名稱 (必填)</div>
                    <div class="param"><strong>start</strong>: 起始頁數 (必填)</div>
                    <div class="param"><strong>end</strong>: 結束頁數 (必填)</div>
                </div>
            </div>
            
            <div class="endpoint">
                <div class="method">GET</div>
                <div class="url">/api/article/{article_id}?board={board}</div>
                <div class="params">
                    <div class="param"><strong>article_id</strong>: 文章 ID (必填)</div>
                    <div class="param"><strong>board</strong>: PTT 看板名稱 (必填)</div>
                </div>
            </div>
            
            <div class="endpoint">
                <div class="method">GET</div>
                <div class="url">/api/search?board={board}&keyword={keyword}</div>
                <div class="params">
                    <div class="param"><strong>board</strong>: PTT 看板名稱 (必填)</div>
                    <div class="param"><strong>keyword</strong>: 搜尋關鍵字 (必填)</div>
                </div>
            </div>

            <div class="endpoint">
                <div class="method">GET</div>
                <div class="url">/api/articles/list?board={board}&start={start_idx}&end={end_idx}</div>
                <div class="params">
                    <div class="param"><strong>board</strong>: PTT 看板名稱 (必填)</div>
                    <div class="param"><strong>start</strong>: 起始頁數 (必填)</div>
                    <div class="param"><strong>end</strong>: 結束頁數 (必填)</div>
                </div>
            </div>
        </body>
    </html>
    """

if __name__ == '__main__':
    # 區分本地開發環境與 Azure 生產環境
    if 'WEBSITE_HOSTNAME' in os.environ:
        # 在 Azure App Service 上運行，讓內建的 web 伺服器處理請求
        app.config['SERVER_NAME'] = os.environ['WEBSITE_HOSTNAME']
        print(f"Running on Azure App Service: {os.environ['WEBSITE_HOSTNAME']}")
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
    else:
        # 本地開發環境
        app.run(host='0.0.0.0', port=5000, debug=True)
