import sys
import json
from PttWebCrawler.crawler import PttWebCrawler


def main(args=None):
    """The main routine."""
    if args is None:
        args = sys.argv[1:]

    # 嘗試使用傳統網頁爬蟲
    try:
        crawler = PttWebCrawler(args, as_lib=True)
        result = crawler.run()
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(f"爬蟲過程中發生錯誤: {e}")
        print(json.dumps({"articles": [], "error": str(e)}, ensure_ascii=False))


if __name__ == "__main__":
    main()