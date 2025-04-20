#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import json
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
import uvicorn

# 创建 FastAPI 应用
app = FastAPI(
    title="小红书内容提取 API",
    description="提取小红书链接中的标题、作者、内容和图片",
    version="1.0.0"
)

def extract_url(text: str) -> str:
    """
    从文本中提取URL
    """
    url_pattern = r"https?://[^\s<>\"]+|www\.[^\s<>\"]+?"
    urls = re.findall(url_pattern, text)
    return urls[0] if urls else text

def scrape_xiaohongshu(url: str) -> Dict[str, Any]:
    """
    从小红书链接中提取信息
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        session = requests.Session()
        response = session.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
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
        
        # 提取作者信息
        author = None
        
        # 1. 尝试完全匹配提供的HTML结构
        name_links = soup.find_all('a', class_='name')
        
        for link in name_links:
            username = link.find('span', class_='username')
            if username:
                author = username.text.strip()
                break
        
        # 2. 如果没找到，尝试直接找所有username span
        if not author:
            all_username_spans = soup.find_all('span', class_='username')
            for span in all_username_spans:
                if span.text.strip():
                    author = span.text.strip()
                    break
        
        # 3. 尝试从页面内容中提取特定模式
        if not author:
            author_pattern = r'作者[：:]\s*([^\s<>"\']+)'
            match = re.search(author_pattern, response.text)
            if match:
                author = match.group(1)
        
        author = author if author else "未知作者"
        
        # 提取图片
        images = []
        
        # 使用正则表达式提取所有图片URL
        img_pattern = r'https?://[^\s<>"\']+?(?:jpg|jpeg|png|webp)(?:[^\s<>"\'\);]*)'
        found_urls = re.findall(img_pattern, response.text)
        
        # 清理和过滤URL
        for url in found_urls:
            # 清理URL，移除可能的后缀字符
            url = re.sub(r'[;)]$', '', url)
            # 只保留http/https链接，并确保URL包含完整的图片路径
            if (url.startswith(('http://', 'https://')) and 
                len(url.split('/')) > 3 and  # 确保URL包含路径部分
                ('jpg' in url or 'jpeg' in url or 'png' in url or 'webp' in url)):  # 确保是图片URL
                # 移除URL中的背景样式相关内容
                url = url.split(');background')[0]
                # 过滤掉头像和图标
                if ('avatar' not in url.lower() and 
                    'icon' not in url.lower() and 
                    'logo' not in url.lower() and
                    url not in images):
                    images.append(url)
        


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
            "images": images[1:],
            "url": url
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提取内容时发生错误: {str(e)}")

# 只保留一个简单的API端点
@app.get("/scrape")
async def scrape_endpoint(url: str = Query(..., description="小红书链接或包含链接的文本")):
    """
    提取小红书内容的API端点
    """
    extracted_url = extract_url(url)
    
    # 验证URL是否为小红书链接
    if "xiaohongshu.com" not in urlparse(extracted_url).netloc:
        return JSONResponse(
            status_code=400,
            content={"error": "提供的URL不是小红书链接"}
        )
    
    # 提取内容
    result = scrape_xiaohongshu(extracted_url)
    return result

# 启动服务器
if __name__ == "__main__":
    uvicorn.run("xiaohongshu_api:app", host="0.0.0.0", port=8000, reload=True)