# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import os
import re
import sys
import json
import requests
import argparse
import time
import random
import codecs
import logging
import socket
import traceback
from datetime import datetime
from bs4 import BeautifulSoup
from six import u
from requests.adapters import HTTPAdapter

# 根據 Python 版本導入不同的 Retry
try:
    # Python 3
    from urllib3.util import Retry
except ImportError:
    try:
        # 較舊版本的 requests
        from requests.packages.urllib3.util.retry import Retry
    except ImportError:
        # 如果都無法導入，定義一個空的 Retry 類
        class Retry:
            pass

__version__ = '1.0'

# if python 2, disable verify flag in requests.get()
VERIFY = True
if sys.version_info[0] < 3:
    VERIFY = False
    requests.packages.urllib3.disable_warnings()


class PttWebCrawler(object):

    PTT_URL = 'https://www.ptt.cc'

    """docstring for PttWebCrawler"""
    def __init__(self, cmdline=None, as_lib=False):
        self.parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description='''
            A crawler for the web version of PTT, the largest online community in Taiwan.
            Input: board name and page indices (or articla ID)
            Output: BOARD_NAME-START_INDEX-END_INDEX.json (or BOARD_NAME-ID.json)
        ''')
        self.parser.add_argument('-b', metavar='BOARD_NAME', help='Board name', required=True)
        group = self.parser.add_mutually_exclusive_group(required=True)
        group.add_argument('-i', metavar=('START_INDEX', 'END_INDEX'), type=int, nargs=2, help="Start and end index")
        group.add_argument('-a', metavar='ARTICLE_ID', help="Article ID")
        self.parser.add_argument('-l', '--list', action='store_true', help="只爬取文章列表（標題、作者、時間、推噓文）而不爬取內容")
        self.parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)

        self.args = None
        if cmdline:
            self.args = self.parser.parse_args(cmdline)
        
        # 如果不是作為函式庫使用，則立即執行爬蟲
        if not as_lib and self.args:
            self.run()
    
    def run(self):
        """
        執行爬蟲並回傳結果
        """
        if not self.args:
            self.args = self.parser.parse_args()
            
        board = self.args.b
        result = {}
        
        if self.args.i:
            start = self.args.i[0]
            if self.args.i[1] == -1:
                end = self.getLastPage(board)
            else:
                end = self.args.i[1]
            
            # 依據是否指定只爬列表決定使用的方法
            if hasattr(self.args, 'list') and self.args.list:
                result = self.parse_list_articles(start, end, board)
            else:
                result = self.parse_articles(start, end, board)
        else:  # self.args.a
            article_id = self.args.a
            result = self.parse_article(article_id, board)
            
        return result

    # def parse_articles(self, start, end, board, path='.', timeout=3):
    #         filename = board + '-' + str(start) + '-' + str(end) + '.json'
    #         filename = os.path.join(path, filename)
    #         self.store(filename, u'{"articles": [', 'w')
    #         for i in range(end-start+1):
    #             index = start + i
    #             print('Processing index:', str(index))
    #             resp = requests.get(
    #                 url = self.PTT_URL + '/bbs/' + board + '/index' + str(index) + '.html',
    #                 cookies={'over18': '1'}, verify=VERIFY, timeout=timeout
    #             )
    #             if resp.status_code != 200:
    #                 print('invalid url:', resp.url)
    #                 continue
    #             soup = BeautifulSoup(resp.text, 'html.parser')
    #             divs = soup.find_all("div", "r-ent")
    #             for div in divs:
    #                 try:
    #                     # ex. link would be <a href="/bbs/PublicServan/M.1127742013.A.240.html">Re: [問題] 職等</a>
    #                     href = div.find('a')['href']
    #                     link = self.PTT_URL + href
    #                     article_id = re.sub('\.html', '', href.split('/')[-1])
    #                     if div == divs[-1] and i == end-start:  # last div of last page
    #                         self.store(filename, self.parse(link, article_id, board), 'a')
    #                     else:
    #                         self.store(filename, self.parse(link, article_id, board) + ',\n', 'a')
    #                 except:
    #                     pass
    #             time.sleep(0.1)
    #         self.store(filename, u']}', 'a')
    #         return filename
    def parse_articles(self, start, end, board, timeout=10):
        """
        爬取指定板塊中的文章列表
        
        Args:
            start: 起始頁碼
            end: 結束頁碼
            board: 板塊名稱
            timeout: 請求超時時間
            
        Returns:
            一個字典，包含爬取到的文章列表
        """
        articles = []
        
        # 建立 Session 保持 cookie
        session = requests.Session()
        
        # 設定模擬瀏覽器 headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.ptt.cc/bbs/index.html',
        }
        
        # 第一次請求獲取 cookies
        try:
            # 先訪問首頁獲取基本 cookie
            print(f"訪問 PTT 首頁獲取 cookie")
            resp = session.get(
                'https://www.ptt.cc/bbs/index.html',
                headers=headers,
                timeout=timeout,
                verify=VERIFY
            )
            
            # 強制設置 over18 cookie
            session.cookies.set('over18', '1', domain='www.ptt.cc')
            
            # 直接訪問目標板塊
            print(f"訪問 {board} 板")
            resp = session.get(
                f'{self.PTT_URL}/bbs/{board}/index.html',
                headers=headers,
                timeout=timeout,
                verify=VERIFY
            )
            
            if resp.status_code != 200:
                print(f"訪問 {board} 板失敗，狀態碼: {resp.status_code}")
                return {'articles': []}
                
            # 獲取最大頁數
            max_page = self.getLastPage(board, timeout)
            print(f"{board} 板最大頁數: {max_page}")
            
            # 確保頁碼在有效範圍內
            if end > max_page:
                end = max_page
                print(f"結束頁碼超過最大頁數，已自動調整為: {end}")
                
        except Exception as e:
            print(f"初始化連接時出錯: {e}")
            return {'articles': []}
        
        # 開始爬取頁面
        for i in range(start, end + 1):
            page_url = f'{self.PTT_URL}/bbs/{board}/index{i}.html'
            print(f"爬取頁面: {page_url}")
            
            try:
                resp = session.get(
                    page_url,
                    headers=headers,
                    timeout=timeout,
                    verify=VERIFY
                )
                
                if resp.status_code != 200:
                    print(f"頁面請求失敗，狀態碼: {resp.status_code}")
                    continue
                
                # 解析 HTML
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 查找所有文章區塊
                article_divs = soup.select('div.r-ent')
                print(f"找到 {len(article_divs)} 個文章區塊")
                
                for div in article_divs:
                    try:
                        # 獲取文章連結
                        title_div = div.select_one('div.title')
                        if not title_div:
                            continue
                            
                        a_tag = title_div.select_one('a')
                        if not a_tag:
                            # 可能是已刪除的文章
                            continue
                            
                        href = a_tag.get('href')
                        if not href or '/bbs/' not in href:
                            continue
                            
                        # 文章標題
                        title = a_tag.text.strip()
                        
                        # 完整的文章 URL
                        article_url = self.PTT_URL + href
                        
                        # 文章 ID
                        article_id = href.split('/')[-1].replace('.html', '')
                        
                        # 作者和日期
                        meta_div = div.select_one('div.meta')
                        author = meta_div.select_one('div.author').text.strip() if meta_div and meta_div.select_one('div.author') else ''
                        date = meta_div.select_one('div.date').text.strip() if meta_div and meta_div.select_one('div.date') else ''
                        
                        # 推文數
                        push_count_div = div.select_one('div.nrec')
                        push_count_str = push_count_div.text.strip() if push_count_div else '0'
                        
                        print(f"爬取文章: {article_id} - {title}")
                        
                        # 獲取文章內容
                        article_json = self.parse(article_url, article_id, board, timeout)
                        article_data = json.loads(article_json)
                        articles.append(article_data)
                        
                        # 避免請求過於頻繁
                        time.sleep(0.5)
                        
                    except Exception as e:
                        print(f"處理文章時出錯: {e}")
                        continue
                
                # 頁面之間的延遲
                time.sleep(1)
                
            except Exception as e:
                print(f"爬取頁面 {page_url} 時出錯: {e}")
                continue
                
        print(f"總共爬取了 {len(articles)} 篇文章")
        return {'articles': articles}


    # def parse_article(self, article_id, board, path='.'):
    #     link = self.PTT_URL + '/bbs/' + board + '/' + article_id + '.html'
    #     filename = board + '-' + article_id + '.json'
    #     filename = os.path.join(path, filename)
    #     self.store(filename, self.parse(link, article_id, board), 'w')
    #     return filename
    def parse_article(self, article_id, board):
        link = self.PTT_URL + f'/bbs/{board}/{article_id}.html'
        result = self.parse(link, article_id, board)
        return json.loads(result)


    @staticmethod
    def parse(link, article_id, board, timeout=3):
        print('Processing article:', article_id)
        
        # 建立 Session 以保持 cookie
        session = requests.Session()
        session.cookies.set('over18', '1', domain='www.ptt.cc')
        
        # 使用更完整的標頭
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 檢查是否在 Azure 環境中運行
        is_azure = 'AZURE_FUNCTIONS_ENVIRONMENT' in os.environ or 'WEBSITE_SITE_NAME' in os.environ
        
        if is_azure:
            print("在 Azure 環境中運行 parse 函數，啟用特殊處理")
            # 增加請求超時
            timeout = max(timeout, 30)
            
            # 修改請求標頭以增加成功率
            if 'Referer' not in headers:
                headers['Referer'] = 'https://www.ptt.cc/bbs/' + board + '/index.html'
                
            # 配置 session
            session.trust_env = False  # 不使用系統代理設定
            
            # 檢查代理配置
            proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
            if proxy:
                proxies = {'http': proxy, 'https': proxy}
                print(f"使用代理: {proxy}")
            else:
                proxies = None
            
            # 嘗試最多 3 次
            max_retries = 3
            for retry in range(max_retries):
                try:
                    print(f"嘗試第 {retry+1}/{max_retries} 次請求")
                    resp = session.get(
                        url=link,
                        headers=headers,
                        verify=VERIFY,
                        timeout=timeout,
                        proxies=proxies,
                        allow_redirects=True
                    )
                    if resp.status_code == 200:
                        break
                    print(f"請求失敗，狀態碼: {resp.status_code}")
                    time.sleep(3)  # 失敗後等待一段時間再重試
                except Exception as e:
                    print(f"請求異常: {e}")
                    if retry == max_retries - 1:
                        raise
                    time.sleep(3)
            else:  # 所有重試都失敗
                return json.dumps({"error": "無法連接到 PTT 網站", "article_id": article_id}, sort_keys=True, ensure_ascii=False)
        else:
            # 非 Azure 環境，使用正常請求
            resp = session.get(
                url=link, 
                headers=headers, 
                verify=VERIFY, 
                timeout=timeout
            )
        
        if resp.status_code != 200:
            print('invalid url:', resp.url)
            return json.dumps({"error": "invalid url", "status_code": resp.status_code}, sort_keys=True, ensure_ascii=False)
        
        # 檢查是否需要年齡驗證
        if '您必須年滿十八歲才能瀏覽此網頁' in resp.text:
            print("需要年齡驗證，嘗試通過...")
            from_url = link.replace(PttWebCrawler.PTT_URL, '')
            resp = session.post(
                'https://www.ptt.cc/ask/over18',
                data={'from': from_url, 'yes': 'yes'},
                headers=headers,
                timeout=timeout,
                verify=VERIFY
            )
            # 再次獲取文章
            resp = session.get(url=link, headers=headers, verify=VERIFY, timeout=timeout)
            if resp.status_code != 200:
                return json.dumps({"error": "age verification failed"}, sort_keys=True, ensure_ascii=False)
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        main_content = soup.find(id="main-content")
        
        if not main_content:
            return json.dumps({"error": "main-content not found", "url": link}, sort_keys=True, ensure_ascii=False)
        metas = main_content.select('div.article-metaline')
        author = ''
        title = ''
        date = ''
        if metas:
            author = metas[0].select('span.article-meta-value')[0].string if metas[0].select('span.article-meta-value')[0] else author
            title = metas[1].select('span.article-meta-value')[0].string if metas[1].select('span.article-meta-value')[0] else title
            date = metas[2].select('span.article-meta-value')[0].string if metas[2].select('span.article-meta-value')[0] else date

            # remove meta nodes
            for meta in metas:
                meta.extract()
            for meta in main_content.select('div.article-metaline-right'):
                meta.extract()

        # remove and keep push nodes
        pushes = main_content.find_all('div', class_='push')
        for push in pushes:
            push.extract()

        try:
            ip = main_content.find(string=re.compile(u'※ 發信站:'))
            ip = re.search('[0-9]*\.[0-9]*\.[0-9]*\.[0-9]*', ip).group()
        except:
            ip = "None"

        # 移除 '※ 發信站:' (starts with u'\u203b'), '◆ From:' (starts with u'\u25c6'), 空行及多餘空白
        # 保留英數字, 中文及中文標點, 網址, 部分特殊符號
        filtered = [ v for v in main_content.stripped_strings if v[0] not in [u'※', u'◆'] and v[:2] not in [u'--'] ]
        expr = re.compile(u(r'[^\u4e00-\u9fa5\u3002\uff1b\uff0c\uff1a\u201c\u201d\uff08\uff09\u3001\uff1f\u300a\u300b\s\w:/-_.?~%()]'))
        for i in range(len(filtered)):
            filtered[i] = re.sub(expr, '', filtered[i])

        filtered = [_f for _f in filtered if _f]  # remove empty strings
        filtered = [x for x in filtered if article_id not in x]  # remove last line containing the url of the article
        content = ' '.join(filtered)
        content = re.sub(r'(\s)+', ' ', content)
        # print 'content', content

        # push messages
        p, b, n = 0, 0, 0
        messages = []
        for push in pushes:
            if not push.find('span', 'push-tag'):
                continue
            push_tag = push.find('span', 'push-tag').string.strip(' \t\n\r')
            push_userid = push.find('span', 'push-userid').string.strip(' \t\n\r')
            # if find is None: find().strings -> list -> ' '.join; else the current way
            push_content = push.find('span', 'push-content').strings
            push_content = ' '.join(push_content)[1:].strip(' \t\n\r')  # remove ':'
            push_ipdatetime = push.find('span', 'push-ipdatetime').string.strip(' \t\n\r')
            messages.append( {'push_tag': push_tag, 'push_userid': push_userid, 'push_content': push_content, 'push_ipdatetime': push_ipdatetime} )
            if push_tag == u'推':
                p += 1
            elif push_tag == u'噓':
                b += 1
            else:
                n += 1

        # count: 推噓文相抵後的數量; all: 推文總數
        message_count = {'all': p+b+n, 'count': p-b, 'push': p, 'boo': b, "neutral": n}

        # print 'msgs', messages
        # print 'mscounts', message_count

        # json data
        data = {
            'url': link,
            'board': board,
            'article_id': article_id,
            'article_title': title,
            'author': author,
            'date': date,
            'content': content,
            'ip': ip,
            'message_count': message_count,
            'messages': messages
        }
        # print 'original:', d
        return json.dumps(data, sort_keys=True, ensure_ascii=False)

    @staticmethod
    def getLastPage(board, timeout=3):
        # 建立 Session 以保持 cookie
        session = requests.Session()
        session.cookies.set('over18', '1', domain='www.ptt.cc')
        
        # 使用更完整的標頭
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        try:
            response = session.get(
                url='https://www.ptt.cc/bbs/' + board + '/index.html',
                headers=headers,
                timeout=timeout,
                verify=VERIFY
            )
            
            if response.status_code != 200:
                print(f"獲取最後頁面時失敗，狀態碼: {response.status_code}")
                return 1
            
            content = response.content.decode('utf-8')
            first_page = re.search(r'href="/bbs/' + board + '/index(\d+).html">&lsaquo;', content)
            
            if first_page is None:
                # 嘗試其他可能的模式
                first_page = re.search(r'href="/bbs/' + board + '/index(\d+).html"', content)
                if first_page is None:
                    print(f"無法解析 {board} 板的最後頁面，使用默認值 1")
                    return 1
            
            return int(first_page.group(1)) + 1
        except Exception as e:
            print(f"獲取最後頁面時出錯: {e}")
            return 1

    @staticmethod
    def store(filename, data, mode):
        with codecs.open(filename, mode, encoding='utf-8') as f:
            f.write(data)

    @staticmethod
    def get(filename, mode='r'):
        with codecs.open(filename, mode, encoding='utf-8') as f:
            return json.load(f)

    def parse_list_articles(self, start, end, board, timeout=10):
        """
        只爬取指定板塊中的文章列表資訊，不進入文章頁面爬取內容
        
        Args:
            start: 起始頁碼
            end: 結束頁碼
            board: 板塊名稱
            timeout: 請求超時時間
            
        Returns:
            一個字典，包含爬取到的文章列表資訊
        """
        articles = []
        error_log = []
        
        # 建立 Session 保持 cookie
        session = requests.Session()
        
        # 使用更完整的瀏覽器標頭，避免被反爬蟲機制識別
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        }
        
        # 隨機選擇一個常見的 User-Agent，增加爬蟲的隱蔽性
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
        ]
        headers['User-Agent'] = random.choice(user_agents)
        
        # 檢查是否在 Azure 環境中運行
        is_azure = 'AZURE_FUNCTIONS_ENVIRONMENT' in os.environ or 'WEBSITE_SITE_NAME' in os.environ
        
        if is_azure:
            print("檢測到在 Azure 環境中運行，啟用特殊處理")
            
            # 增加連接超時時間
            timeout = max(timeout, 60)
            
            # 設置最大重試次數
            max_retries = 3
            
            # 在 Azure 中使用代理可能有幫助（僅用於測試）
            # 注意：如需使用代理，請在 Azure 中設置環境變數
            proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
            if proxy:
                proxies = {
                    'http': proxy,
                    'https': proxy
                }
                print(f"使用代理服務器: {proxy}")
            else:
                proxies = None
                
        else:
            max_retries = 1
            proxies = None
        
        # 處理 cookie 的特殊邏輯
        try:
            # 直接設定年齡驗證 cookie
            session.cookies.set('over18', '1', domain='www.ptt.cc')
            
            # 直接訪問目標板塊
            print(f"訪問 {board} 板")
            board_url = f'{self.PTT_URL}/bbs/{board}/index.html'
            
            # 使用循環進行重試
            for retry in range(max_retries):
                try:
                    resp = session.get(
                        board_url,
                        headers=headers,
                        timeout=timeout,
                        verify=VERIFY,
                        allow_redirects=True,  # 允許重定向
                        proxies=proxies
                    )
                    
                    if resp.status_code == 200:
                        break
                    
                    print(f"嘗試 {retry+1}/{max_retries} 失敗，狀態碼: {resp.status_code}")
                    
                    # 只有在 Azure 環境中才嘗試使用不同的請求方式
                    if is_azure and retry < max_retries - 1:
                        # 短暫延遲後再重試
                        time.sleep(5)
                        
                        # 更換 User-Agent
                        headers['User-Agent'] = random.choice(user_agents)
                        
                        # 嘗試直接使用更簡單的標頭
                        if retry == 1:
                            # 簡化請求標頭
                            simple_headers = {
                                'User-Agent': headers['User-Agent'],
                                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                            }
                            headers = simple_headers
                            print("使用簡化的請求標頭重試")
                
                except Exception as e:
                    print(f"訪問嘗試 {retry+1}/{max_retries} 發生異常: {e}")
                    if retry == max_retries - 1:
                        raise
                    time.sleep(5)
            
            # 檢查板塊是否存在
            if resp.status_code != 200:
                error_msg = f"訪問 {board} 板失敗，狀態碼: {resp.status_code}，可能板塊不存在或已被暫停"
                print(error_msg)
                error_log.append(error_msg)
                return {'articles': [], 'errors': error_log}
            
            # 檢查是否需要年齡驗證（有些板塊會單獨需要）
            if '您必須年滿十八歲才能瀏覽此網頁' in resp.text:
                print(f"{board} 板需要年齡驗證，嘗試通過...")
                resp = session.post(
                    'https://www.ptt.cc/ask/over18',
                    data={'from': f'/bbs/{board}/index.html', 'yes': 'yes'},
                    headers=headers,
                    timeout=timeout,
                    verify=VERIFY
                )
                if resp.status_code != 200:
                    error_msg = f"板塊 {board} 年齡驗證失敗，狀態碼: {resp.status_code}"
                    print(error_msg)
                    error_log.append(error_msg)
                    return {'articles': [], 'errors': error_log}
                
                # 再次訪問板塊
                resp = session.get(
                    board_url,
                    headers=headers,
                    timeout=timeout,
                    verify=VERIFY
                )
            
            # 獲取最大頁數
            try:
                max_page = self.getLastPage(board, timeout)
                print(f"{board} 板最大頁數: {max_page}")
                
                # 確保頁碼在有效範圍內
                if start <= 0:
                    start = 1
                    print(f"起始頁碼小於等於0，已自動調整為: {start}")
                
                if end > max_page:
                    end = max_page
                    print(f"結束頁碼超過最大頁數，已自動調整為: {end}")
            except Exception as e:
                error_msg = f"獲取最大頁數時出錯: {e}"
                print(error_msg)
                error_log.append(error_msg)
                # 如果無法獲取最大頁數，使用合理的預設值
                if end > 10000:
                    end = 10000  # 設定一個合理的上限
                    print(f"無法獲取最大頁數，設定結束頁碼為: {end}")
                
        except Exception as e:
            error_msg = f"初始化連接時出錯: {e}"
            print(error_msg)
            error_log.append(error_msg)
            return {'articles': [], 'errors': error_log}
        
        # 開始爬取頁面
        for i in range(start, end + 1):
            page_url = f'{self.PTT_URL}/bbs/{board}/index{i}.html'
            print(f"爬取頁面: {page_url}")
            
            try:
                resp = session.get(
                    page_url,
                    headers=headers,
                    timeout=timeout,
                    verify=VERIFY
                )
                
                if resp.status_code != 200:
                    error_msg = f"頁面請求失敗，狀態碼: {resp.status_code}"
                    print(error_msg)
                    error_log.append(error_msg)
                    continue
                
                # 解析 HTML
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # 查找所有文章區塊
                try:
                    article_divs = soup.select('div.r-ent')
                    print(f"找到 {len(article_divs)} 個文章區塊")
                    
                    # 如果找不到文章區塊，可能是頁面結構變化或反爬蟲機制
                    if len(article_divs) == 0:
                        # 嘗試其他選擇器
                        article_divs = soup.find_all("div", class_="r-ent")
                        print(f"使用 find_all 方法找到 {len(article_divs)} 個文章區塊")
                        
                        if len(article_divs) == 0:
                            error_msg = f"在頁面 {page_url} 中找不到文章區塊，可能被反爬蟲機制阻擋或頁面結構變化"
                            print(error_msg)
                            error_log.append(error_msg)
                            
                            # 保存頁面內容以便調試
                            debug_file = f"debug_{board}_{i}.html"
                            with open(debug_file, 'w', encoding='utf-8') as f:
                                f.write(resp.text)
                            print(f"已將頁面內容保存到 {debug_file} 以便調試")
                            
                            # 嘗試檢查頁面內容中是否有特定提示
                            page_content = resp.text.lower()
                            if 'over18' in page_content or '年滿十八歲' in page_content:
                                print("疑似年齡驗證問題，重新嘗試設定 cookie")
                                # 重新設定 cookie 後重試
                                session.cookies.clear()
                                session.cookies.set('over18', '1', domain='www.ptt.cc')
                                # 不重試，繼續下一頁
                            continue
                except Exception as e:
                    error_msg = f"解析 HTML 時發生錯誤: {e}"
                    print(error_msg)
                    error_log.append(error_msg)
                    continue
                
                for div in article_divs:
                    try:
                        # 獲取文章連結
                        title_div = div.select_one('div.title')
                        if not title_div:
                            continue
                            
                        a_tag = title_div.select_one('a')
                        if not a_tag:
                            # 可能是已刪除的文章，但我們仍然記錄標題
                            title = title_div.text.strip()
                            article_url = None
                            article_id = None
                        else:
                            href = a_tag.get('href')
                            if not href or '/bbs/' not in href:
                                continue
                                
                            # 文章標題
                            title = a_tag.text.strip()
                            
                            # 完整的文章 URL
                            article_url = self.PTT_URL + href
                            
                            # 文章 ID
                            article_id = href.split('/')[-1].replace('.html', '')
                        
                        # 作者和日期
                        meta_div = div.select_one('div.meta')
                        author = meta_div.select_one('div.author').text.strip() if meta_div and meta_div.select_one('div.author') else ''
                        date = meta_div.select_one('div.date').text.strip() if meta_div and meta_div.select_one('div.date') else ''
                        
                        # 推文數
                        push_count_div = div.select_one('div.nrec')
                        push_count_text = push_count_div.text.strip() if push_count_div else '0'
                        
                        # 解析推文數
                        if push_count_text == '爆':
                            push_count = 100
                        elif push_count_text.startswith('X'):
                            if push_count_text == 'XX':
                                push_count = -100
                            else:
                                try:
                                    push_count = -int(push_count_text[1:]) if push_count_text[1:].isdigit() else 0
                                except:
                                    push_count = 0
                        else:
                            try:
                                push_count = int(push_count_text) if push_count_text.isdigit() else 0
                            except:
                                push_count = 0
                        
                        # 建立文章資訊字典
                        article_info = {
                            'title': title,
                            'url': article_url,
                            'article_id': article_id,
                            'author': author,
                            'date': date,
                            'push_count': push_count,
                            'push_count_text': push_count_text
                        }
                        
                        articles.append(article_info)
                        
                    except Exception as e:
                        error_msg = f"處理文章列表項目時出錯: {e}"
                        print(error_msg)
                        error_log.append(error_msg)
                        continue
                
                # 頁面之間的延遲，隨機化以避免被識別為爬蟲
                sleep_time = 0.5 + random.random() * 1.5  # 0.5 到 2 秒之間
                time.sleep(sleep_time)
                
            except Exception as e:
                error_msg = f"爬取頁面 {page_url} 時出錯: {e}"
                print(error_msg)
                error_log.append(error_msg)
                continue
                
        print(f"總共爬取了 {len(articles)} 篇文章列表資訊")
        result = {'articles': articles}
        if error_log:
            result['errors'] = error_log
        return result

if __name__ == '__main__':
    c = PttWebCrawler()
