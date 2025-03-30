import json
import argparse
from anytree import Node, RenderTree
from anytree.exporter import DotExporter

def load_sitemap(filename):
    """Загружает sitemap из JSON файла"""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_tree(data, parent_node=None):
    """Рекурсивно строит дерево из данных sitemap"""
    if parent_node is None:
        root = Node(f"{data['url']} ({data['status']})")
        for child in data['links']:
            build_tree(child, root)
        return root
    else:
        child_node = Node(f"{data['url']} ({data['status']})", parent=parent_node)
        for child in data['links']:
            build_tree(child, child_node)

def visualize_tree(tree, output_format='text'):
    """Визуализирует дерево в разных форматах"""
    if output_format == 'text':
        # Текстовая визуализация в консоли
        for pre, _, node in RenderTree(tree):
            print(f"{pre}{node.name}")
    elif output_format == 'dot':
        # Экспорт в DOT формат для Graphviz
        DotExporter(tree).to_dotfile('tree.dot')
        print("Дерево экспортировано в tree.dot. Используйте Graphviz для визуализации.")
    elif output_format == 'png':
        # Прямой экспорт в PNG (требуется Graphviz)
        try:
            DotExporter(tree).to_picture('tree.png')
            print("Дерево экспортировано в tree.png")
        except Exception as e:
            print(f"Ошибка при экспорте в PNG: {e}. Убедитесь, что Graphviz установлен.")
    else:
        print("Неизвестный формат вывода. Используйте 'text', 'dot' или 'png'.")

def main():
    # Настройка парсера аргументов командной строки
    parser = argparse.ArgumentParser(description='Визуализатор дерева ссылок из sitemap.json')
    parser.add_argument('-i', '--input', default='sitemap.json', 
                       help='Имя входного JSON файла (по умолчанию: sitemap.json)')
    parser.add_argument('-o', '--output', default='text', 
                       choices=['text', 'dot', 'png'],
                       help='Формат вывода: text, dot или png (по умолчанию: text)')
    
    args = parser.parse_args()
    
    try:
        # Загрузка данных
        sitemap_data = load_sitemap(args.input)
        
        # Построение дерева
        tree = build_tree(sitemap_data)
        
        # Визуализация
        print(f"Визуализация дерева из файла {args.input}:")
        visualize_tree(tree, args.output)
        
    except FileNotFoundError:
        print(f"Ошибка: файл {args.input} не найден.")
    except json.JSONDecodeError:
        print(f"Ошибка: файл {args.input} не является валидным JSON.")
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")

if __name__ == "__main__":
    main()