import argparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
import time
import json
from collections import deque
import sqlite3

class DatabaseManager:
    def __init__(self, db_name="crawler.db"):
        self.db_name = db_name
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            # Таблица для processed_urls
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_urls (
                    url TEXT PRIMARY KEY
                )
            ''')
            # Таблица для sitemap
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sitemap (
                    url TEXT PRIMARY KEY,
                    status INTEGER,
                    redirected_from TEXT,
                    parent_url TEXT,
                    FOREIGN KEY (parent_url) REFERENCES sitemap(url)
                )
            ''')
            conn.commit()

    def clear_db(self):
        """Очистка всех данных из таблиц"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM processed_urls')
            cursor.execute('DELETE FROM sitemap')
            conn.commit()
    def add_processed_url(self, url):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO processed_urls (url) VALUES (?)', (url,))
            conn.commit()

    def is_url_processed(self, url):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT url FROM processed_urls WHERE url = ?', (url,))
            return cursor.fetchone() is not None

    def add_sitemap_node(self, url, status=None, redirected_from=None, parent_url=None):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO sitemap (url, status, redirected_from, parent_url)
                VALUES (?, ?, ?, ?)
            ''', (url, status, redirected_from, parent_url))
            conn.commit()

    def update_node_status(self, url, status):
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE sitemap SET status = ? WHERE url = ?', (status, url))
            conn.commit()

    def get_sitemap_json(self, root_url):
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            def build_node(url):
                cursor.execute('SELECT * FROM sitemap WHERE url = ?', (url,))
                row = cursor.fetchone()
                if not row:
                    return None
                
                node = {
                    "url": row["url"],
                    "status": row["status"],
                    "redirected_from": row["redirected_from"],
                    "links": []
                }
                
                cursor.execute('SELECT url FROM sitemap WHERE parent_url = ?', (url,))
                child_urls = cursor.fetchall()
                for child_url in child_urls:
                    child_node = build_node(child_url["url"])
                    if child_node:
                        node["links"].append(child_node)
                
                return node
            
            return build_node(root_url)

class LinkChecker:
    def __init__(self, base_url, delay=1, timeout=50, url_count_limit=20, depth_limit=1000, file="sitemap.json"):
        self.base_url = self.normalize_url(base_url)
        self.domain = urlparse(self.base_url).netloc
        self.db = DatabaseManager()
        self.delay = delay
        self.timeout = timeout
        self.url_count_limit = url_count_limit
        self.depth_limit = depth_limit
        self.output_file = file
        self.url_count = 0
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def normalize_url(self, url):
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        url, _ = urldefrag(url)
        parsed = urlparse(url)
        # Сохраняем конечный слэш, если он был в исходном URL
        path = parsed.path
        if url.endswith('/') and not path.endswith('/'):
            path += '/'
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def is_valid_url(self, url):
        parsed = urlparse(url)
        return bool(parsed.netloc) and bool(parsed.scheme) and parsed.netloc == self.domain

    def process_url(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout, 
                                 allow_redirects=True, stream=True)
            content = b''
            for chunk in response.iter_content(1024*10):
                content += chunk
                if len(content) > 1024*1024*2:
                    break
            status_code = response.status_code
            final_url = self.normalize_url(response.url)
            
            if response.history:
                for redirect in response.history:
                    print(f"Перенаправление: {redirect.url} -> {redirect.status_code}")
                print(f"Конечный URL: {final_url} - Статус: {status_code}")
            else:
                print(f"Проверка: {url} - Статус: {status_code}")
            
            links = set()
            if status_code == 200:
                soup = BeautifulSoup(content, 'html.parser')
                for link in soup.find_all('a', href=True):
                    absolute_url = urljoin(final_url, link['href'])
                    normalized_url = self.normalize_url(absolute_url)
                    if (self.is_valid_url(normalized_url) and 
                        normalized_url != final_url and 
                        normalized_url not in links):
                        links.add(normalized_url)
            
            return links, status_code, final_url
        except requests.RequestException as e:
            print(f"Ошибка при проверке {url}: {e}")
            return set(), str(e), url

    def build_sitemap(self):
        queue = deque([(self.base_url, 0)])
        self.db.add_sitemap_node(self.base_url)
        self.db.add_processed_url(self.base_url)

        while queue and self.url_count < self.url_count_limit:
            current_url, depth = queue.popleft()
            
            if depth > self.depth_limit:
                continue

            self.url_count += 1
            links, status, final_url = self.process_url(current_url)
            
            if final_url != current_url:
                self.db.add_sitemap_node(final_url, status, current_url, None)
            else:
                self.db.update_node_status(current_url, status)

            time.sleep(self.delay)

            for link in links:
                if not self.db.is_url_processed(link):
                    self.db.add_sitemap_node(link, None, None, final_url)
                    self.db.add_processed_url(link)
                    if depth + 1 <= self.depth_limit:
                        queue.append((link, depth + 1))

    def start(self):
        print(f"Начинаем проверку сайта: {self.base_url}")
        print(f"Параметры: delay={self.delay}s, timeout={self.timeout}s, " +
              f"url_count_limit={self.url_count_limit}, depth_limit={self.depth_limit}")
        
        self.build_sitemap()
        sitemap = self.db.get_sitemap_json(self.base_url)
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(sitemap, f, ensure_ascii=False, indent=2)
        
        print("\nРезультаты сохранены в "+self.output_file)
        return sitemap

def main():
    parser = argparse.ArgumentParser(description='Проверка ссылок на сайте')
    parser.add_argument('url', help='URL сайта для проверки')
    parser.add_argument('--delay', type=float, default=1, help='Задержка между запросами (секунды)')
    parser.add_argument('--timeout', type=float, default=50, help='Таймаут запроса (секунды)')
    parser.add_argument('--url-count-limit', type=int, default=1000000, help='Лимит URL для проверки')
    parser.add_argument('--depth-limit', type=int, default=1000, help='Максимальная глубина проверки')
    parser.add_argument('--output', default="sitemap.json", help='Файл')
    
    args = parser.parse_args()

    checker = LinkChecker(
        args.url,
        delay=args.delay,
        timeout=args.timeout,
        url_count_limit=args.url_count_limit,
        depth_limit=args.depth_limit,
        file=args.output
    )

    checker.start()

if __name__ == "__main__":
    main()