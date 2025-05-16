import os
import sys
import logging

# 設定全局環境配置
if 'AZURE_FUNCTIONS_ENVIRONMENT' in os.environ or 'WEBSITE_SITE_NAME' in os.environ:
    logging.info("在 Azure 環境中執行，應用特殊配置")
    # 在 Azure 環境中執行特殊配置
    import ssl
    try:
        # 在某些情況下，Azure 可能需要特殊的 SSL 配置
        ssl._create_default_https_context = ssl._create_unverified_context
        logging.info("已配置 SSL 上下文為非驗證模式")
    except Exception as e:
        logging.warning(f"SSL 配置失敗: {e}")

from PttWebCrawler.crawler import PttWebCrawler

__all__ = ['PttWebCrawler']