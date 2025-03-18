import asyncio
from bilibili_api import video
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bilibili-mcp")

@mcp.tool()
def get_video_info(bvid: str) -> dict:
    """Get video info by BV number"""
    v = video.Video(bvid=bvid)
    info = asyncio.run(v.get_info())
    return info
