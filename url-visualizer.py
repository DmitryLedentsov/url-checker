import json
import argparse
from anytree import Node, RenderTree, find_by_attr
from anytree.exporter import DotExporter

def load_sitemap(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_tree(data, parent_node=None):
    if data.get('redirected_from'):
        label = f"{data['redirected_from']} -> {data['url']}"
    else:
        label = data['url']

    status = data.get('status')
    if status is not None:
        label += f" ({status})"
    
    # Add search result info if present
    result = data.get('result')
    if result == 'FOUND':
        label += " [TEXT FOUND]"
    
    if parent_node is None:
        root = Node(label, status=status, original_url=data['url'], result=result)
        for child in data.get('links', []):
            build_tree(child, root)
        return root
    else:
        child_node = Node(label, parent=parent_node, status=status, original_url=data['url'], result=result)
        for child in data.get('links', []):
            build_tree(child, child_node)

def find_start_node(tree, start_url):
    """Находит узел по URL или части URL"""
    return find_by_attr(tree, name='original_url', value=start_url)

def check_int(s):
    return str(s).isdigit()

def nodeattrfunc(node):
    """Функция для определения атрибутов узла в Graphviz"""
    attrs = []
    
    # Status-based styling
    if node.status is not None:
        if not check_int(node.status):  # client side error
            attrs.append('color=red')
            attrs.append('style=filled')
            attrs.append('fillcolor="#ffea00"')
        elif int(node.status) >= 400 and int(node.status) < 500:  # 4xx - клиентские ошибки
            attrs.append('color=red')
            attrs.append('style=filled')
            attrs.append('fillcolor="#ffdddd"')
        elif int(node.status) >= 500:  # 5xx - серверные ошибки
            attrs.append('color=red')
            attrs.append('style=filled')
            attrs.append('fillcolor="#ffaaaa"')
    
    # Search result styling
    if hasattr(node, 'result') and node.result == 'FOUND':
        attrs.append('style=filled')
        attrs.append('fillcolor="#ae00ff"')
        attrs.append('color=red')
    
    return ', '.join(attrs) if attrs else ''

def visualize_tree(tree, output_format='text'):
    if output_format == 'text':
        for pre, _, node in RenderTree(tree):
            print(f"{pre}{node.name}")
    elif output_format == 'dot':
        DotExporter(tree,
                   nodeattrfunc=nodeattrfunc,
                   options=['rankdir=LR']).to_dotfile('tree.dot')
        print("Дерево экспортировано в tree.dot. Используйте Graphviz для визуализации.")
    else:
        print("Неизвестный формат вывода. Используйте 'text' или 'dot'.")

def main():
    parser = argparse.ArgumentParser(description='Визуализатор дерева ссылок из sitemap.json')
    parser.add_argument('-i', '--input', default='sitemap.json', 
                       help='Имя входного JSON файла (по умолчанию: sitemap.json)')
    parser.add_argument('-o', '--output', default='text', 
                       choices=['text', 'dot'],
                       help='Формат вывода: text, dot (по умолчанию: text)')
    parser.add_argument('--start', 
                       help='URL начальной ноды для визуализации (часть URL или полный URL)')
    
    args = parser.parse_args()
    
    try:
        sitemap_data = load_sitemap(args.input)
        full_tree = build_tree(sitemap_data)
        
        # Если указан аргумент --start, находим соответствующую ноду
        if args.start:
            start_node = find_start_node(full_tree, args.start)
            if not start_node:
                # ищем по части урла
                for node in full_tree.descendants:
                    if args.start in node.original_url:
                        start_node = node
                        break
                
                if not start_node:
                    print(f"Ошибка: нода с URL содержащим '{args.start}' не найдена.")
                    print("Доступные корневые ноды:")
                    for child in full_tree.children:
                        print(f" - {child.original_url}")
                    return  
            tree = start_node
            print(f"Визуализация поддерева начиная с: {args.start}")
        else:
            tree = full_tree
            print(f"Визуализация полного дерева из файла {args.input}:")

        visualize_tree(tree, args.output)
        
    except FileNotFoundError:
        print(f"Ошибка: файл {args.input} не найден.")
    except json.JSONDecodeError:
        print(f"Ошибка: файл {args.input} не является валидным JSON.")
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")

if __name__ == "__main__":
    main()