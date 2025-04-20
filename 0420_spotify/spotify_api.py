#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from urllib.parse import urlparse
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List
import uvicorn
from datetime import datetime
import requests
import ssl

# 创建 FastAPI 应用
app = FastAPI(
    title="Spotify 播客内容提取 API",
    description="使用官方API提取 Spotify 播客链接中的信息，包括标题、描述、时长等",
    version="1.0.0"
)

def extract_url(text: str) -> str:
    """
    从文本中提取URL
    """
    url_pattern = r"https?://[^\s<>\"]+|www\.[^\s<>\"]+?"
    urls = re.findall(url_pattern, text)
    return urls[0] if urls else text

def format_duration(duration_ms: int) -> str:
    """
    将毫秒转换为可读的时长格式 (HH:MM:SS)
    """
    seconds = duration_ms // 1000
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def extract_timestamps(description: str) -> List[Dict[str, str]]:
    """
    从描述中提取时间戳信息
    """
    timestamps = []
    # 匹配时间戳格式 (例如: 00:00 - 介绍)
    timestamp_pattern = r'(\d{1,2}:)?(\d{1,2}:\d{2})\s*[-–]\s*(.+?)(?=\n|$)'
    matches = re.finditer(timestamp_pattern, description)
    
    for match in matches:
        time_str = match.group(1) + match.group(2) if match.group(1) else match.group(2)
        description_text = match.group(3).strip()
        timestamps.append({
            "time": time_str,
            "description": description_text
        })
    
    return timestamps

def scrape_spotify_podcast(url: str) -> Dict[str, Any]:
    """
    使用 Spotify API 获取播客信息
    """
    try:
        # 设置 Spotify API 客户端
        client_credentials_manager = SpotifyClientCredentials(
            client_id='f77fd4ab760e46fdbf09a64249e6924e',
            client_secret='2551dfbdb1a54c41b7c40901f6847f39'
        )
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        
        # 从URL中提取episode ID
        episode_id = url.split('/')[-1].split('?')[0]
        
        # 获取播客集信息
        episode = sp.episode(episode_id)
        
        # 获取时间戳
        timestamps = extract_timestamps(episode['description'])
        
        # 格式化返回数据
        return {
            "podcast_name": episode['show']['name'],
            "episode_title": episode['name'],
            "description": episode['description'],
            "upload_date": episode['release_date'],
            "duration": format_duration(episode['duration_ms']),
            "timestamps": timestamps,
            "content": "需要 Spotify Premium 订阅才能访问完整转录文本",
            "url": url,
            "image": episode['images'][0]['url'] if episode['images'] else None,
            "additional_info": {
                "language": episode['language'],
                "explicit": episode['explicit'],
                "show_url": episode['show']['external_urls']['spotify']
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取播客信息时发生错误: {str(e)}")

@app.get("/scrape")
async def scrape_endpoint(url: str = Query(..., description="Spotify播客链接")):
    """
    提取Spotify播客内容的API端点
    """
    extracted_url = extract_url(url)
    
    # 验证URL是否为Spotify链接
    if "spotify.com" not in urlparse(extracted_url).netloc:
        return JSONResponse(
            status_code=400,
            content={"error": "提供的URL不是Spotify链接"}
        )
    
    # 提取内容
    result = scrape_spotify_podcast(extracted_url)
    return result

# 启动服务器
if __name__ == "__main__":
    import uvicorn
    import ssl
    
    # 添加测试函数
    def test_api():
        try:
            response = requests.get(
                "https://localhost:8000/scrape?url=https://open.spotify.com/episode/6kIWYhK6y34ua0YBaSm1ru",
                verify=False
            )
            print("Status Code:", response.status_code)
            print("Response:", response.json())
        except Exception as e:
            print("Error:", str(e))
    
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain('cert.pem', 'key.pem')
    # 明确设置支持的协议版本
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_context.maximum_version = ssl.TLSVersion.TLSv1_3
    
    # 启动服务器
    uvicorn.run(
        "spotify_api:app",  # 使用字符串形式指定应用
        host="0.0.0.0",
        port=8000,
        ssl_keyfile="key.pem",
        ssl_certfile="cert.pem",
        reload=True
    ) 