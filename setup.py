try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name = 'PttWebCrawler',
    packages = ['PttWebCrawler'],
    version = '1.4',
    description = 'PTT 網路爬蟲 API 服務 - 基於 jwlin/ptt-web-crawler 專案的擴展',
    author = 'GarfieldHuang',  # 已更新您的名字
    author_email = 'garfield.huang@example.com',  # 請替換為您的電子郵件
    url = 'https://github.com/GarfieldHuang/ptt-web-crawler',  # 已更新您的GitHub用戶名
    download_url = 'https://github.com/GarfieldHuang/ptt-web-crawler/archive/v1.4.tar.gz',  # 已更新您的GitHub用戶名
    keywords = ['ptt', 'crawler', 'web', 'api', 'flask'],
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    license='MIT',
    install_requires=[
        'argparse',
        'beautifulsoup4',
        'requests',
        'six',
        'pyOpenSSL'
    ],
    entry_points={
        'console_scripts': [
            'PttWebCrawler = PttWebCrawler.__main__:main'
        ]
    },
    zip_safe=True
)
