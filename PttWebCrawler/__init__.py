import os
import sys
import logging

# 設置基本日誌配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 導入 Azure 輔助函式並初始化
try:
    from PttWebCrawler.azure_helpers import setup_for_azure
    # 設定 Azure 環境
    setup_for_azure()
except Exception as e:
    logging.error(f"導入或設定 Azure 輔助函式時出錯: {e}")
    # 進行基本的 Azure 環境配置
    if 'AZURE_FUNCTIONS_ENVIRONMENT' in os.environ or 'WEBSITE_SITE_NAME' in os.environ:
        logging.info("在 Azure 環境中運行，進行基本配置")
        try:
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
            logging.info("已設置 SSL 上下文為非驗證模式")
        except:
            pass

from PttWebCrawler.crawler import PttWebCrawler

__all__ = ['PttWebCrawler']