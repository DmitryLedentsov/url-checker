import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
import time
import json
import argparse

TIMEOUT = 50
#LIMIT=20
def normalize_url(url):
    """Удаляет fragment identifier из URL и нормализует его"""
    url, _ = urldefrag(url)
    return url

def check_links(start_url):
    visited = set()
    count= 0
    to_visit = [normalize_url(start_url)]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    sitemap = {
        "url": normalize_url(start_url),
        "status": None,
        "redirects": []
    }
    
    url_nodes = {normalize_url(start_url): sitemap}

    while to_visit:
        url = to_visit.pop(0)
        
        if url in visited:
            continue
            
        #if(count>LIMIT):
        #    continue
        #count+=1
        visited.add(url)
        current_node = url_nodes[url]
        
        try:
            response = requests.get(url, headers=headers, timeout=TIMEOUT)
            status_code = response.status_code
            
            print(f"Проверка: {url} - Статус: {status_code}")
            
            current_node["status"] = status_code
            
            if status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.find_all('a', href=True):
                    absolute_url = urljoin(url, link['href'])
                    normalized_url = normalize_url(absolute_url)
                    
                    # Обрабатываем только ссылки на том же домене
                    if urlparse(normalized_url).netloc == urlparse(start_url).netloc:
                        if normalized_url not in url_nodes:
                            new_node = {
                                "url": normalized_url,
                                "status": None,
                                "redirects": []
                            }
                            current_node["redirects"].append(new_node)
                            url_nodes[normalized_url] = new_node
                            
                        if normalized_url not in visited:
                            to_visit.append(normalized_url)
            
            time.sleep(1)
            
        except requests.RequestException as e:
            current_node["status"] = str(e)
            print(f"Ошибка при проверке {url}: {e}")
            
    return sitemap

def main():
    parser = argparse.ArgumentParser(description='Проверка ссылок на сайте')
    parser.add_argument('url', help='URL сайта для проверки (например, https://example.com)')
    args = parser.parse_args()
    
    website = args.url.strip()
    if not website.startswith(('http://', 'https://')):
        website = 'https://' + website
    
    print(f"Начинаем проверку сайта: {website}")
    sitemap = check_links(website)
    
    with open('sitemap.json', 'w', encoding='utf-8') as f:
        json.dump(sitemap, f, ensure_ascii=False, indent=2)
    
    print("\nРезультаты сохранены в sitemap.json")

if __name__ == "__main__":
    main()