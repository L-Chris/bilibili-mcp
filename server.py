import asyncio
from bilibili_api import video
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bilibili-mcp")

@mcp.tool()
async def get_video_info(bvid: str) -> dict:
    """Get video info by BV number"""
    v = video.Video(bvid=bvid)
    info = await v.get_info()
    return info

mcp.run()
