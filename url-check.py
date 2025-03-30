import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
TIMEOUT=50
def check_links(start_url):
    # Множество для хранения проверенных URL
    visited = set()
    # Список для хранения непроверенных URL
    to_visit = [start_url]
    # Словари для хранения результатов
    broken_links = {}
    valid_links = 0

    # Заголовки для имитации браузера
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    while to_visit:
        url = to_visit.pop(0)
        
        if url in visited:
            continue
            
        visited.add(url)
        
        try:
            response = requests.get(url, headers=headers, timeout=TIMEOUT)
            status_code = response.status_code
            
            print(f"Проверка: {url} - Статус: {status_code}")
            
            if status_code == 200:
                valid_links += 1
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.find_all('a', href=True):
                    absolute_url = urljoin(url, link['href'])
                    if urlparse(absolute_url).netloc == urlparse(start_url).netloc:
                        if absolute_url not in visited:
                            to_visit.append(absolute_url)
            else:
                broken_links[url] = status_code
                
            time.sleep(1)
            
        except requests.RequestException as e:
            broken_links[url] = str(e)
            print(f"Ошибка при проверке {url}: {e}")
            
    # Вывод общих результатов
    print("\n=== Результаты проверки ===")
    print(f"Всего проверено ссылок: {len(visited)}")
    print(f"Рабочих ссылок: {valid_links}")
    print(f"Нерабочих ссылок: {len(broken_links)}")
    
    # Отдельный вывод нерабочих ссылок
    if broken_links:
        print("\n=== Список нерабочих ссылок ===")
        print(f"Найдено нерабочих ссылок: {len(broken_links)}")
        print("-" * 50)
        for url, error in broken_links.items():
            print(f"URL: {url}")
            print(f"Ошибка: {error}")
            print("-" * 50)
    else:
        print("\nНерабочие ссылки не найдены!")

def main():
    website = input("Введите URL сайта для проверки (например, https://example.com): ").strip()
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    print(f"Начинаем проверку сайта: {website}")
    check_links(website)

if __name__ == "__main__":
    main()