import asyncio
import os
import aiohttp
from datetime import datetime
from tabulate import tabulate
from bilibili_api import video, Credential, search
from mcp.server.fastmcp import FastMCP
from bcut_asr import get_audio_subtitle_async

# 从环境变量获取认证信息
SESSDATA = os.getenv('sessdata')
BILI_JCT = os.getenv('bili_jct')
BUVID3 = os.getenv('buvid3')

# 初始化 Credential
credential = Credential(sessdata=SESSDATA, bili_jct=BILI_JCT, buvid3=BUVID3)

MCP_HOST = os.getenv('MCP_HOST', '127.0.0.1')
try:
    MCP_PORT = int(os.getenv('MCP_PORT', '8000'))
except ValueError:
    MCP_PORT = 8000

mcp = FastMCP("bilibili-mcp", host=MCP_HOST, port=MCP_PORT)

@mcp.tool("search_video", description="搜索bilibili视频，支持按发布时间范围和排序方式筛选")
async def search_video(
    keyword: str,
    page: int = 1,
    page_size: int = 20,
    time_start: str = "",
    time_end: str = "",
    order_type: str = "totalrank",
) -> str:
    """
    keyword: 搜索关键词
    page: 页码，默认1
    page_size: 每页数量，默认20
    time_start: 发布时间起始，格式 YYYY-MM-DD，如 "2024-01-01"
    time_end: 发布时间截止，格式 YYYY-MM-DD，如 "2024-06-30"
    order_type: 排序方式，可选 totalrank(综合)/click(播放量)/pubdate(发布时间)/dm(弹幕)/stow(收藏)/scores(评论)
    """
    order_map = {
        "totalrank": search.OrderVideo.TOTALRANK,
        "click": search.OrderVideo.CLICK,
        "pubdate": search.OrderVideo.PUBDATE,
        "dm": search.OrderVideo.DM,
        "stow": search.OrderVideo.STOW,
        "scores": search.OrderVideo.SCORES,
    }
    search_result = await search.search_by_type(
        keyword,
        search_type=search.SearchObjectType.VIDEO,
        page=page,
        page_size=page_size,
        time_start=time_start or None,
        time_end=time_end or None,
        order_type=order_map.get(order_type, search.OrderVideo.TOTALRANK),
    )
    
    # 准备表格数据
    table_data = []
    headers = ["发布日期", "标题", "UP主", "时长", "播放量", "点赞数", "类别", "bvid"]
    
    for video in search_result["result"]:
        # 转换发布时间
        pubdate = datetime.fromtimestamp(video["pubdate"]).strftime("%Y/%m/%d")
        
        # 将标题转换为Markdown链接格式
        title_link = f"[{video['title']}]({video['arcurl']})"
        
        table_data.append([
            pubdate,
            title_link,
            video["author"],
            video["duration"],
            video["play"],
            video["like"],
            video["typename"],
            video["bvid"]
        ])
    
    # 使用 tabulate 生成 Markdown 表格
    return tabulate(table_data, headers=headers, tablefmt="pipe")

@mcp.tool("get_video_subtitle", description="获取bilibili视频的字幕，需提供视频BV号，支持 txt/srt/raw 格式")
async def get_video_subtitle(bvid: str, format: str = "txt") -> dict:
    """
    bvid: 视频BV号
    format: 字幕格式，txt(纯文本，默认)/srt(带时间戳)/raw(原始时间戳数据)
    """
    v = video.Video(bvid=bvid, credential=credential)
    cid = await v.get_cid(page_index=0)
    info = await v.get_player_info(cid=cid)
    json_files = info.get("subtitle", {}).get("subtitles", [])

    target_subtitle = None
    for subtitle in json_files:
        if subtitle.get("lan") == "ai-zh":
            target_subtitle = subtitle
            break

    if not target_subtitle:
        url_res = await v.get_download_url(cid=cid)
        audio_arr = url_res.get('dash', {}).get('audio', [])
        if not audio_arr:
            return "没有找到AI生成的中文字幕"

        audio = audio_arr[-1]
        # 优先选 mcdn URL（Bcut 只能访问 B站内部 CDN）
        all_urls = [audio['baseUrl']] + audio.get('backupUrl', [])
        audio_url = ""
        for u in all_urls:
            if '.mcdn.bilivideo.cn' in u:
                audio_url = u
                break
        if not audio_url:
            audio_url = audio['baseUrl']

        return await get_audio_subtitle_async(audio_url, format)

    subtitle_url = target_subtitle["subtitle_url"]
    if not subtitle_url.startswith(('http://', 'https://')):
        subtitle_url = f"https:{subtitle_url}"

    async with aiohttp.ClientSession() as session:
        async with session.get(subtitle_url) as response:
            subtitle_content = await response.json()
            if "body" not in subtitle_content:
                return subtitle_content

            if format == "srt":
                lines = []
                for n, item in enumerate(subtitle_content["body"], 1):
                    lines.append(f"{n}\n{item['from']:.3f} --> {item['to']:.3f}\n{item['content']}\n")
                return "\n".join(lines)
            elif format == "raw":
                return subtitle_content["body"]
            else:
                return "".join(item["content"] for item in subtitle_content["body"])

@mcp.tool("get_video_info", description="获取bilibili视频信息，需提供视频BV号")
async def get_video_info(bvid: str) -> dict:
    """
    bvid: 视频BV号
    """
    v = video.Video(bvid=bvid, credential=credential)
    info = await v.get_info()
    return info

@mcp.tool("get_media_subtitle", description="获取媒体文件的AI中文字幕，需提供媒体文件URL")
async def get_media_subtitle(url: str) -> dict:
    """
    url: 媒体文件URL
    """
    asr_data = await get_audio_subtitle_async(url)
    return asr_data

if __name__ == "__main__":
    mcp.run(transport=os.getenv('MCP_TRANSPORT', 'stdio'))
