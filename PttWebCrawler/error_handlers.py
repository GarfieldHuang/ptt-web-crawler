# -*- coding: utf-8 -*-
"""
API 錯誤處理模組
"""

import os
import sys
import logging
import socket
import traceback
import json
import requests

def get_azure_diagnostic_info():
    """獲取 Azure 環境的診斷資訊"""
    diagnostic_info = {
        'is_azure': 'AZURE_FUNCTIONS_ENVIRONMENT' in os.environ or 'WEBSITE_SITE_NAME' in os.environ,
        'python_version': sys.version,
        'hostname': 'unknown',
        'ptt_dns': 'unknown'
    }
    
    # 嘗試獲取主機名
    try:
        diagnostic_info['hostname'] = socket.gethostname()
    except:
        pass
    
    # 嘗試 DNS 解析 PTT
    try:
        ptt_ip = socket.gethostbyname('www.ptt.cc')
        diagnostic_info['ptt_dns'] = ptt_ip
    except Exception as e:
        diagnostic_info['ptt_dns_error'] = str(e)
    
    # 獲取 Azure 相關環境變數
    diagnostic_info['azure_env'] = {k: v for k, v in os.environ.items() 
                            if k.startswith('AZURE_') or k.startswith('WEBSITE_')}
    
    # 獲取代理設定
    diagnostic_info['proxy'] = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy') or 'none'
    
    # 獲取請求庫資訊
    try:
        diagnostic_info['requests_version'] = requests.__version__
    except:
        pass
    
    return diagnostic_info

def get_error_response(e, request_info=None):
    """獲取格式化的錯誤響應"""
    error_response = {
        "error": str(e),
        "diagnosis": {
            "runtime_env": get_azure_diagnostic_info(),
            "exception": str(e),
            "traceback": traceback.format_exc().split('\n')
        }
    }
    
    if request_info:
        error_response["diagnosis"]["request_info"] = request_info
    
    return error_response
