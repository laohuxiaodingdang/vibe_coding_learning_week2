#!/usr/bin/env python3
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import json
import time
import os

def extract_url(text):
    """
    从文本中提取URL
    """
    url_pattern = r"https?://[^\s<>\"]+|www\.[^\s<>\"]+?"
    urls = re.findall(url_pattern, text)
    return urls[0] if urls else text

def scrape_xiaohongshu(url):
    """
    从小红书链接中提取信息
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    
    try:
        session = requests.Session()
        response = session.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 打印HTML内容以便调试
        print("页面内容预览：")
        print(response.text[:500])
        
        # 提取标题
        title = None
        title_selectors = [
            'div#detail-title.title',
            'div[data-v-610be4fa].title',
            'div.title',
            'meta[property="og:title"]',
            'title'
        ]
        
        for selector in title_selectors:
            if selector.startswith('meta'):
                element = soup.find('meta', property='og:title')
                if element:
                    title = element.get('content')
                    break
            else:
                element = soup.select_one(selector)
                if element:
                    title = element.text.strip()
                    break
        
        title = title if title else "未找到标题"
        print(f"找到的标题: {title}")  # 调试信息

        # 提取作者信息
        author = None

        try:
            # 方法1：直接找到 username span
            author_span = soup.find('span', {
                'class': 'username',
                'data-v-701599c8': ''
            })
            if author_span:
                author = author_span.text.strip()
                print(f"方法1找到作者: {author}")

            # 方法2：通过父元素链接找到 username span
            if not author:
                author_link = soup.find('a', {
                    'class': 'name',
                    'data-v-701599c8': ''
                })
                if author_link:
                    author_span = author_link.find('span', class_='username')
                    if author_span:
                        author = author_span.text.strip()
                        print(f"方法2找到作者: {author}")

            # 如果还是没找到，使用更宽松的查找
            if not author:
                username_spans = soup.find_all('span', class_='username')
                for span in username_spans:
                    if span.text.strip():
                        author = span.text.strip()
                        print(f"备用方法找到作者: {author}")
                        break

            author = author if author else "未知作者"
            print(f"最终找到的作者: {author}")

        except Exception as e:
            print(f"提取作者时出错: {e}")
            author = "未知作者" 
                    
        

        # 提取图片 - 更新的图片提取逻辑
        images = []
        
        # 1. 尝试获取所有图片标签
        all_images = soup.find_all('img')
        
        for img in all_images:
            # 获取所有可能的图片URL属性
            src = img.get('src')
            data_src = img.get('data-src')
            data_lazy = img.get('data-lazy')
            data_original = img.get('data-original')
            
            # 检查所有可能的图片URL
            possible_urls = [src, data_src, data_lazy, data_original]
            
            for url in possible_urls:
                if url and url.strip():
                    # 确保URL是完整的
                    if url.startswith('//'):
                        url = 'https:' + url
                    elif url.startswith('/'):
                        url = 'https://www.xiaohongshu.com' + url
                    
                    # 过滤掉小图标和无关图片
                    if ('avatar' not in url.lower() and 
                        'icon' not in url.lower() and 
                        'logo' not in url.lower() and
                        url not in images):
                        images.append(url)
        
        # 2. 尝试从页面源码中提取图片URL
        img_pattern = r'https?://[^\s<>"\']+?(?:jpg|jpeg|png|webp)(?:[^\s<>"\']*)'
        found_urls = re.findall(img_pattern, response.text)
        
        for url in found_urls:
            if ('avatar' not in url.lower() and 
                'icon' not in url.lower() and 
                'logo' not in url.lower() and
                url not in images):
                images.append(url)
        
        # 3. 尝试从特定的数据属性中提取
        for element in soup.find_all(attrs={'data-xhs-img': True}):
            url = element.get('data-xhs-img')
            if url and url not in images:
                if url.startswith('//'):
                    url = 'https:' + url
                images.append(url)

        # 4. 尝试从 script 标签中提取图片URL
        for script in soup.find_all('script', type='application/json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    # 递归搜索字典中的图片URL
                    def extract_urls(obj):
                        if isinstance(obj, str):
                            if re.match(r'https?://.*?(?:jpg|jpeg|png|webp)', obj):
                                if obj not in images:
                                    images.append(obj)
                        elif isinstance(obj, dict):
                            for value in obj.values():
                                extract_urls(value)
                        elif isinstance(obj, list):
                            for item in obj:
                                extract_urls(item)
                    
                    extract_urls(data)
            except:
                continue


        # 提取文字内容
        text_content = ""
        content_selectors = [".content", ".note-content", ".desc", "article"]
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content:
                text_content = content.get_text(strip=True)
                break
        
        if not text_content:
            text_content = "未找到文字内容"
        
        return {
            "title": title,
            "author": author,
            "content": text_content,
            "images": images,
            "url": url
        }
        
    except Exception as e:
        print(f"错误: {str(e)}")
        print("错误详情:", e.__class__.__name__)
        import traceback
        print("堆栈跟踪:", traceback.format_exc())
        return None

def save_to_html(data, filename="xiaohongshu_result.html"):
    """
    将数据保存为HTML文件
    """
    try:
        html_template = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    background-color: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #333;
                    border-bottom: 2px solid #eee;
                    padding-bottom: 10px;
                    margin-bottom: 5px;
                }}
                .author {{
                    color: #666;
                    font-size: 0.9em;
                    margin-bottom: 20px;
                }}
                .content {{
                    margin: 20px 0;
                    line-height: 1.6;
                }}
                .image-container {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                    gap: 20px;
                    margin-top: 20px;
                }}
                .image-item {{
                    background: white;
                    padding: 10px;
                    border-radius: 5px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }}
                .image-item img {{
                    width: 100%;
                    height: auto;
                    border-radius: 5px;
                }}
                .image-item a {{
                    display: block;
                    text-decoration: none;
                    color: #666;
                    margin-top: 5px;
                    word-break: break-all;
                }}
                .source-link {{
                    margin-top: 20px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{title}</h1>
                <div class="author">作者：{author}</div>
                <div class="content">{content}</div>
                <div class="image-container">
                    {image_items}
                </div>
                <div class="source-link">
                    <p>原文链接：<a href="{url}" target="_blank">{url}</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # 生成图片HTML
        image_items = []
        for i, img_url in enumerate(data['images'], 1):
            image_item = f"""
            <div class="image-item">
                <a href="{img_url}" target="_blank">
                    <img src="{img_url}" alt="图片 {i}">
                </a>
                <a href="{img_url}" target="_blank">查看原图</a>
            </div>
            """
            image_items.append(image_item)
        
        # 填充模板
        html_content = html_template.format(
            title=data['title'],
            author=data['author'],
            content=data['content'],
            image_items='\n'.join(image_items),
            url=data['url']
        )
        
        # 保存HTML文件
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"数据已保存到 {filename}")
        
        # 同时保存JSON格式
        json_filename = filename.rsplit('.', 1)[0] + '.json'
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"原始数据已保存到 {json_filename}")
        
        # 获取文件的绝对路径
        abs_path = os.path.abspath(filename)
        print(f"\n请在浏览器中打开以下链接查看结果：")
        print(f"file://{abs_path}")
        
    except Exception as e:
        print(f"保存文件时发生错误: {e}")

def main():
    user_input = input("请输入小红书链接或包含链接的文本: ")
    url = extract_url(user_input)
    print(f"处理URL: {url}")
    
    data = scrape_xiaohongshu(url)
    if data:
        save_to_html(data)
    else:
        print("获取数据失败")

if __name__ == "__main__":
    main()