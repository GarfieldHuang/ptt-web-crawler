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
import codecs
from bs4 import BeautifulSoup
from six import u

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
        resp = requests.get(url=link, cookies={'over18': '1'}, verify=VERIFY, timeout=timeout)
        if resp.status_code != 200:
            print('invalid url:', resp.url)
            return json.dumps({"error": "invalid url"}, sort_keys=True, ensure_ascii=False)
        soup = BeautifulSoup(resp.text, 'html.parser')
        main_content = soup.find(id="main-content")
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
        content = requests.get(
            url= 'https://www.ptt.cc/bbs/' + board + '/index.html',
            cookies={'over18': '1'}, timeout=timeout
        ).content.decode('utf-8')
        first_page = re.search(r'href="/bbs/' + board + '/index(\d+).html">&lsaquo;', content)
        if first_page is None:
            return 1
        return int(first_page.group(1)) + 1

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
                        elif push_count_text == 'X1':
                            push_count = -10
                        elif push_count_text == 'X2':
                            push_count = -20
                        elif push_count_text == 'X3':
                            push_count = -30
                        elif push_count_text == 'X4':
                            push_count = -40
                        elif push_count_text == 'X5':
                            push_count = -50
                        elif push_count_text == 'X6':
                            push_count = -60
                        elif push_count_text == 'X7':
                            push_count = -70
                        elif push_count_text == 'X8':
                            push_count = -80
                        elif push_count_text == 'X9':
                            push_count = -90
                        elif push_count_text == 'XX':
                            push_count = -100
                        elif push_count_text.startswith('X'):
                            push_count = -int(push_count_text.replace('X', '')) if push_count_text.replace('X', '').isdigit() else 0
                        else:
                            push_count = int(push_count_text) if push_count_text.isdigit() else 0
                        
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
                        print(f"處理文章列表項目時出錯: {e}")
                        continue
                
                # 頁面之間的延遲
                time.sleep(0.5)
                
            except Exception as e:
                print(f"爬取頁面 {page_url} 時出錯: {e}")
                continue
                
        print(f"總共爬取了 {len(articles)} 篇文章列表資訊")
        return {'articles': articles}

if __name__ == '__main__':
    c = PttWebCrawler()
