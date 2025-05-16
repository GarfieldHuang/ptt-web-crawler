# -*- coding: utf-8 -*-
"""
Azure 環境輔助函式，用於 PTT Web Crawler 在 Azure App Service 上運行時的特殊處理
"""

import os
import sys
import logging
import requests
import socket
import time

# 檢測是否在 Azure 環境中運行
IS_AZURE = 'AZURE_FUNCTIONS_ENVIRONMENT' in os.environ or 'WEBSITE_SITE_NAME' in os.environ

def setup_for_azure():
    """設置 Azure 環境特殊配置"""
    if not IS_AZURE:
        return False
        
    logging.info("在 Azure 環境中運行，設置特殊配置")
    
    try:
        # SSL 設定
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        logging.info("已設置 SSL 上下文為非驗證模式")
    except Exception as e:
        logging.warning(f"設置 SSL 上下文失敗: {e}")
    
    try:
        # 禁用 SSL 警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        logging.info("已禁用 SSL 警告")
    except Exception as e:
        logging.warning(f"禁用 SSL 警告失敗: {e}")
    
    try:
        # 設置較長的默認超時
        socket.setdefaulttimeout(60)
        logging.info("已設置默認 socket 超時為 60 秒")
    except Exception as e:
        logging.warning(f"設置 socket 超時失敗: {e}")
    
    # 顯示一些診斷資訊
    try:
        logging.info(f"環境變數: Python {sys.version}")
        logging.info(f"Requests 版本: {requests.__version__}")
        logging.info(f"主機名稱: {socket.gethostname()}")
        
        # 嘗試對 PTT 進行 DNS 查詢
        try:
            ptt_ip = socket.gethostbyname('www.ptt.cc')
            logging.info(f"PTT DNS 解析結果: {ptt_ip}")
        except Exception as e:
            logging.warning(f"無法解析 PTT IP: {e}")
    except Exception as e:
        logging.warning(f"獲取環境資訊失敗: {e}")
    
    return True

def configure_session_for_azure(session, timeout=30):
    """為 Azure 環境配置 requests session"""
    if not IS_AZURE:
        return session
    
    # 增加超時時間
    timeout = max(timeout, 60)
    
    # 設置基本屬性
    session.trust_env = False  # 不使用系統代理設定
    
    # 增加重試機制
    try:
        # 設置重試適配器
        from requests.adapters import HTTPAdapter
        try:
            # 嘗試從 urllib3 導入 Retry
            from urllib3.util.retry import Retry
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST"]
            )
        except (ImportError, AttributeError):
            # 舊版本 requests
            try:
                from requests.packages.urllib3.util.retry import Retry
                retry_strategy = Retry(
                    total=3,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                    method_whitelist=["HEAD", "GET", "OPTIONS", "POST"]
                )
            except (ImportError, AttributeError):
                # 使用自定義的 HTTPAdapter
                adapter = HTTPAdapter(max_retries=3)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                return session
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
    except Exception as e:
        logging.warning(f"配置重試機制失敗: {e}")
    
    # 配置代理
    proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    if proxy:
        session.proxies = {"http": proxy, "https": proxy}
        logging.info(f"使用代理: {proxy}")
    
    return session

def get_request_with_retry(session, url, headers, timeout=60, max_retries=3, verify=True):
    """
    使用重試機制進行 HTTP GET 請求，專為 Azure 環境設計
    """
    proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    proxies = {'http': proxy, 'https': proxy} if proxy else None
    
    for retry in range(max_retries):
        try:
            logging.info(f"嘗試第 {retry+1}/{max_retries} 次請求: {url}")
            
            # 不同重試使用不同的策略
            if retry > 0:
                # 簡化請求標頭
                simple_headers = {
                    'User-Agent': headers.get('User-Agent', 'Mozilla/5.0'),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
                current_headers = simple_headers
            else:
                current_headers = headers
            
            response = session.get(
                url=url,
                headers=current_headers, 
                timeout=timeout,
                verify=verify,
                proxies=proxies,
                allow_redirects=True
            )
            
            if response.status_code == 200:
                logging.info(f"請求成功，狀態碼: 200")
                return response
            else:
                logging.warning(f"請求失敗，狀態碼: {response.status_code}")
                # 如果是最後一次重試，仍然返回響應
                if retry == max_retries - 1:
                    return response
                
                # 短暫延遲後再重試
                time.sleep(5)
                
        except Exception as e:
            logging.error(f"請求異常: {e}")
            if retry == max_retries - 1:
                raise
            time.sleep(5)
    
    # 這裡不應該到達，但為了安全起見
    raise Exception("所有重試都失敗")
