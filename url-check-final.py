import argparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
import time
import sqlite3
import json
import sys
import os
from requests.exceptions import RequestException

class LinkChecker:
    def __init__(self, base_url, delay=1, timeout=50, url_count_limit=20, depth_limit=1000, db_path='sitemap.db'):
        self.base_url = self.normalize_url(base_url)
        self.domain = urlparse(self.base_url).netloc
        self.delay = delay
        self.timeout = timeout
        self.url_count_limit = url_count_limit
        self.depth_limit = depth_limit
        self.url_count = 0
        self.db_path = db_path
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self._init_db()
        print(f"Инициализация LinkChecker для {self.base_url}")

    def _init_db(self):
        """Инициализация SQLite базы данных"""
        if not os.path.exists(self.db_path):
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''
                    CREATE TABLE IF NOT EXISTS nodes (
                        url TEXT PRIMARY KEY,
                        status TEXT,
                        redirected_from TEXT,
                        parent_url TEXT,
                        depth INTEGER
                    )
                ''')
                c.execute('''
                    CREATE TABLE IF NOT EXISTS processed_urls (
                        url TEXT PRIMARY KEY
                    )
                ''')
                conn.commit()
        else:
            print(f"Используется существующая база данных: {self.db_path}")

    def normalize_url(self, url):
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            url, _ = urldefrag(url)
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')
        except Exception as e:
            print(f"Ошибка нормализации URL {url}: {e}")
            return url

    def is_valid_url(self, url):
        parsed = urlparse(url)
        return bool(parsed.netloc) and bool(parsed.scheme) and parsed.netloc == self.domain

    def process_url(self, url):
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True)
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
                # Ограничиваем объем данных для парсинга
                soup = BeautifulSoup(response.text[:1024*1024], 'html.parser')  # Ограничиваем до 1MB
                for link in soup.find_all('a', href=True):
                    absolute_url = urljoin(final_url, link['href'])
                    normalized_url = self.normalize_url(absolute_url)
                    if (self.is_valid_url(normalized_url) and 
                        normalized_url != final_url and 
                        normalized_url not in links):
                        links.add(normalized_url)
                    if len(links) >= 100:  # Ограничение на количество ссылок с одной страницы
                        break
                soup.decompose()  # Очищаем память после парсинга
            del response  # Явно освобождаем память
            return links, status_code, final_url
        except RequestException as e:
            print(f"Ошибка при проверке {url}: {e}")
            return set(), str(e), url
        except Exception as e:
            print(f"Неизвестная ошибка при обработке {url}: {e}")
            return set(), "Unknown error", url

    def is_processed(self, url, conn):
        """Проверка, был ли URL уже обработан"""
        c = conn.cursor()
        c.execute("SELECT url FROM processed_urls WHERE url = ?", (url,))
        return c.fetchone() is not None

    def add_processed_url(self, url, conn):
        """Добавление URL в список обработанных"""
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO processed_urls (url) VALUES (?)", (url,))

    def save_node(self, url, status, depth, redirected_from=None, parent_url=None, conn=None):
        """Сохранение узла в базу данных"""
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO nodes (url, status, redirected_from, parent_url, depth)
            VALUES (?, ?, ?, ?, ?)
        """, (url, status, redirected_from, parent_url, depth))

    def build_sitemap(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT url FROM nodes WHERE url = ?", (self.base_url,))
            root_exists = c.fetchone() is not None

            if not root_exists:
                self.save_node(self.base_url, None, 0, None, None, conn)
                self.add_processed_url(self.base_url, conn)
                conn.commit()
                queue = deque([(self.base_url, 0, None)])
            else:
                queue = deque([])
                c.execute("SELECT url, parent_url, depth FROM nodes WHERE status IS NULL")
                for url, parent_url, depth in c.fetchall():
                    if depth < self.depth_limit:
                        queue.append((url, depth, parent_url))

            while queue and self.url_count < self.url_count_limit:
                current_url, depth, parent_url = queue.popleft()
                
                if depth > self.depth_limit:
                    print(f"Превышена глубина {depth} для {current_url}")
                    continue

                self.url_count += 1
                links, status, final_url = self.process_url(current_url)
                
                if final_url != current_url:
                    self.save_node(final_url, status, depth, current_url, parent_url, conn)
                else:
                    self.save_node(current_url, status, depth, None, parent_url, conn)
                self.add_processed_url(final_url, conn)
                conn.commit()  # Фиксируем изменения после каждого URL

                for link in links:
                    if not self.is_processed(link, conn):
                        self.save_node(link, None, depth + 1, None, final_url, conn)
                        self.add_processed_url(link, conn)
                        if depth + 1 <= self.depth_limit:
                            queue.append((link, depth + 1, final_url))
                conn.commit()  # Фиксируем новые ссылки

        return self._build_json_sitemap()

    def _build_json_sitemap(self):
        """Построение JSON структуры из базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT url, status, redirected_from FROM nodes WHERE parent_url IS NULL")
            root = c.fetchone()
            if not root:
                return {}

            sitemap = {
                "url": root[0],
                "status": root[1],
                "redirected_from": root[2],
                "links": []
            }

            def add_children(parent_url, parent_node):
                c.execute("SELECT url, status, redirected_from FROM nodes WHERE parent_url = ?", (parent_url,))
                for child in c.fetchall():
                    child_node = {
                        "url": child[0],
                        "status": child[1],
                        "redirected_from": child[2],
                        "links": []
                    }
                    parent_node["links"].append(child_node)
                    add_children(child[0], child_node)

            add_children(root[0], sitemap)
            return sitemap

    def start(self):
        print(f"Начинаем проверку сайта: {self.base_url}")
        print(f"Параметры: delay={self.delay}s, timeout={self.timeout}s, "
              f"url_count_limit={self.url_count_limit}, depth_limit={self.depth_limit}")
        
        try:
            sitemap = self.build_sitemap()
            with open('sitemap.json', 'w', encoding='utf-8') as f:
                json.dump(sitemap, f, ensure_ascii=False, indent=2)
            print("\nРезультаты сохранены в sitemap.json")
            return sitemap
        except Exception as e:
            print(f"Ошибка при сохранении результатов: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Проверка ссылок на сайте')
    parser.add_argument('url', help='URL сайта для проверки')
    parser.add_argument('--delay', type=float, default=1, help='Задержка между запросами (секунды)')
    parser.add_argument('--timeout', type=float, default=50, help='Таймаут запроса (секунды)')
    parser.add_argument('--url-count-limit', type=int, default=1000000, help='Лимит URL для проверки')
    parser.add_argument('--depth-limit', type=int, default=1000, help='Максимальная глубина проверки')
    
    args = parser.parse_args()

    checker = LinkChecker(
        args.url,
        delay=args.delay,
        timeout=args.timeout,
        url_count_limit=args.url_count_limit,
        depth_limit=args.depth_limit
    )

    try:
        checker.start()
    except Exception as e:
        print(f"Служба завершилась с ошибкой: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()