import argparse
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
import time
import json
from collections import deque

class LinkChecker:
    def __init__(self, base_url, delay=1, timeout=50, url_count_limit=20, depth_limit=1000):
        self.base_url = self.normalize_url(base_url)
        self.domain = urlparse(self.base_url).netloc
        self.visited = {}  # Хранит полные узлы
        self.processed_urls = set()  # Отслеживает обработанные URL для предотвращения циклов
        self.delay = delay
        self.timeout = timeout
        self.url_count_limit = url_count_limit
        self.depth_limit = depth_limit
        self.url_count = 0
        self.default_params = {
            'delay': 1,
            'timeout': 50,
            'url_count_limit': 20,
            'depth_limit': 1000
        }
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def normalize_url(self, url):
        """Remove fragment identifier and normalize URL"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        url, _ = urldefrag(url)
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip('/')

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
                soup = BeautifulSoup(response.text, 'html.parser')
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
        root_node = {
            "url": self.base_url,
            "status": None,
            "redirected_from": None,
            "links": []
        }
        self.visited[self.base_url] = root_node
        self.processed_urls.add(self.base_url)  # Добавляем начальный URL как обработанный

        while queue and self.url_count < self.url_count_limit:
            current_url, depth = queue.popleft()
            
            if depth > self.depth_limit:
                continue

            self.url_count += 1
            links, status, final_url = self.process_url(current_url)
            
            if final_url != current_url:
                if current_url in self.visited:
                    node = self.visited.pop(current_url)
                    node["url"] = final_url
                    node["redirected_from"] = current_url
                    self.visited[final_url] = node
                else:
                    self.visited[final_url] = {
                        "url": final_url,
                        "status": status,
                        "redirected_from": current_url,
                        "links": []
                    }
            else:
                self.visited[current_url]["status"] = status
                if "redirected_from" not in self.visited[current_url]:
                    self.visited[current_url]["redirected_from"] = None

            time.sleep(self.delay)

            for link in links:
                # Проверяем, не был ли этот URL уже обработан
                if link not in self.processed_urls:
                    new_node = {
                        "url": link,
                        "status": None,
                        "redirected_from": None,
                        "links": []
                    }
                    self.visited[final_url]["links"].append(new_node)
                    self.visited[link] = new_node
                    self.processed_urls.add(link)  # Помечаем как обработанный
                    if depth + 1 <= self.depth_limit:
                        queue.append((link, depth + 1))

        return root_node

    def start(self):
        print(f"Начинаем проверку сайта: {self.base_url}")
        print(f"Параметры: delay={self.delay}s, timeout={self.timeout}s, " +
              f"url_count_limit={self.url_count_limit}, depth_limit={self.depth_limit}")
        
        sitemap = self.build_sitemap()
        
        with open('sitemap.json', 'w', encoding='utf-8') as f:
            json.dump(sitemap, f, ensure_ascii=False, indent=2)
        
        print("\nРезультаты сохранены в sitemap.json")
        return sitemap

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

    checker.start()

if __name__ == "__main__":
    main()