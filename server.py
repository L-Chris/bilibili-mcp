import asyncio
import os
import aiohttp
from bilibili_api import video, Credential, search
from mcp.server.fastmcp import FastMCP

# 从环境变量获取认证信息
SESSDATA = os.getenv('sessdata')
BILI_JCT = os.getenv('bili_jct')
BUVID3 = os.getenv('buvid3')

# 初始化 Credential
credential = Credential(sessdata=SESSDATA, bili_jct=BILI_JCT, buvid3=BUVID3)

mcp = FastMCP("bilibili-mcp")

@mcp.tool()
async def search_video(keyword: str, page: int = 1, page_size: int = 20) -> dict:
    """搜索视频"""
    search_result = await search.search_by_type(keyword, search_type=search.SearchObjectType.VIDEO, page=page, page_size=page_size)
    return search_result

@mcp.tool()
async def get_video_info(bvid: str) -> dict:
    """Get video info by BV number"""
    v = video.Video(bvid=bvid, credential=credential)
    info = await v.get_info()
    return info

@mcp.tool()
async def get_video_subtitle(bvid: str) -> dict:
    """获取视频的AI中文字幕"""
    v = video.Video(bvid=bvid, credential=credential)
    cid = await v.get_cid(page_index=0)
    info = await v.get_player_info(cid=cid)
    json_files = info["subtitle"]["subtitles"]
    
    # 过滤查找符合条件的字幕
    target_subtitle = None
    for subtitle in json_files:
        if subtitle["lan"] == "ai-zh" and subtitle["lan_doc"] == "中文（自动生成）":
            target_subtitle = subtitle
            break
    
    if not target_subtitle:
        return "没有找到AI生成的中文字幕"
    
    # 确保 URL 有 HTTPS 前缀
    subtitle_url = target_subtitle["subtitle_url"]
    if not subtitle_url.startswith(('http://', 'https://')):
        subtitle_url = f"https:{subtitle_url}"
    
    # 使用 aiohttp 获取字幕内容
    async with aiohttp.ClientSession() as session:
        async with session.get(subtitle_url) as response:
            subtitle_content = await response.json()
            # 提取并拼接所有字幕文本
            if "body" in subtitle_content:
                subtitle_text = "\n".join(item["content"] for item in subtitle_content["body"])
                return subtitle_text
            else:
                return subtitle_content

mcp.run()
