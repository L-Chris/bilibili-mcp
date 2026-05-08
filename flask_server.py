import asyncio
import logging
import os
import sys
from datetime import datetime

import aiohttp
from bilibili_api import Credential, search, video
from flask import Flask, jsonify, request

from bcut_asr import get_audio_subtitle_async

# 从环境变量获取认证信息
SESSDATA = os.getenv("sessdata")
BILI_JCT = os.getenv("bili_jct")
BUVID3 = os.getenv("buvid3")

credential = Credential(sessdata=SESSDATA, bili_jct=BILI_JCT, buvid3=BUVID3)

app = Flask(__name__)


def _run_async(coro):
    return asyncio.run(coro)


ORDER_MAP = {
    "totalrank": search.OrderVideo.TOTALRANK,
    "click": search.OrderVideo.CLICK,
    "pubdate": search.OrderVideo.PUBDATE,
    "dm": search.OrderVideo.DM,
    "stow": search.OrderVideo.STOW,
    "scores": search.OrderVideo.SCORES,
}


async def _search_video_async(
    keyword: str,
    page: int = 1,
    page_size: int = 20,
    time_start: str = "",
    time_end: str = "",
    order_type: str = "totalrank",
) -> dict:
    search_result = await search.search_by_type(
        keyword,
        search_type=search.SearchObjectType.VIDEO,
        page=page,
        page_size=page_size,
        time_start=time_start or None,
        time_end=time_end or None,
        order_type=ORDER_MAP.get(order_type, search.OrderVideo.TOTALRANK),
    )

    items = []

    for item in search_result.get("result", []):
        item["pubdate"] = datetime.fromtimestamp(item["pubdate"]).strftime("%Y/%m/%d")
        items.append(item)

    return {
        "keyword": keyword,
        "page": page,
        "page_size": page_size,
        "total": len(items),
        "items": items,
    }


async def _get_video_subtitle_async(bvid: str, format: str = "txt"):
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
        audio_arr = url_res.get("dash", {}).get("audio", [])
        if not audio_arr:
            return "没有找到AI生成的中文字幕"

        audio = audio_arr[-1]
        audio_url = ""
        if ".mcdn.bilivideo.cn" in audio["baseUrl"]:
            audio_url = audio["baseUrl"]
        else:
            backup_url = audio.get("backupUrl", [])
            if backup_url and "upos-sz" in backup_url[0]:
                audio_url = audio["baseUrl"]
            else:
                audio_url = backup_url[0] if backup_url else audio["baseUrl"]

        return await get_audio_subtitle_async(audio_url, format)

    subtitle_url = target_subtitle["subtitle_url"]
    if not subtitle_url.startswith(("http://", "https://")):
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
            return "".join(item["content"] for item in subtitle_content["body"])


async def _get_video_info_async(bvid: str) -> dict:
    v = video.Video(bvid=bvid, credential=credential)
    return await v.get_info()


async def _get_video_pbp_async(bvid: str, page_index: int | None = None, cid: int | None = None):
    v = video.Video(bvid=bvid, credential=credential)

    if cid is None and page_index is None:
        page_index = 0

    if cid is None:
        cid = await v.get_cid(page_index=page_index)

    return await v.get_pbp(page_index=page_index, cid=cid)


async def _get_media_subtitle_async(url: str, format: str = "txt"):
    return await get_audio_subtitle_async(url, format)


ENDPOINT_PARAMS = {
    "/api/video/search": [
        {"name": "keyword", "type": "str", "required": True, "desc": "搜索关键词"},
        {"name": "page", "type": "int", "required": False, "default": 1, "desc": "页码"},
        {"name": "page_size", "type": "int", "required": False, "default": 20, "desc": "每页数量"},
        {"name": "time_start", "type": "str", "required": False, "default": "", "desc": "发布时间起始，格式 YYYY-MM-DD"},
        {"name": "time_end", "type": "str", "required": False, "default": "", "desc": "发布时间截止，格式 YYYY-MM-DD"},
        {"name": "order_type", "type": "str", "required": False, "default": "totalrank", "desc": "排序方式: totalrank/click/pubdate/dm/stow/scores"},
    ],
    "/api/video/info/<string:bvid>": [
        {"name": "bvid", "type": "str (path)", "required": True, "desc": "视频BV号"},
    ],
    "/api/video/pbp/<string:bvid>": [
        {"name": "bvid", "type": "str (path)", "required": True, "desc": "视频BV号"},
        {"name": "page_index", "type": "int", "required": False, "default": 0, "desc": "分P索引"},
        {"name": "cid", "type": "int", "required": False, "desc": "分P的cid，优先于page_index"},
    ],
    "/api/video/subtitle/<string:bvid>": [
        {"name": "bvid", "type": "str (path)", "required": True, "desc": "视频BV号"},
        {"name": "format", "type": "str", "required": False, "default": "txt", "desc": "字幕格式: txt(纯文本)/srt(带时间戳)/raw(原始时间戳数据)"},
    ],
    "/api/media/subtitle": [
        {"name": "url", "type": "str (body)", "required": True, "desc": "媒体文件URL"},
        {"name": "format", "type": "str (body)", "required": False, "default": "txt", "desc": "字幕格式: txt(纯文本)/srt(带时间戳)/raw(原始时间戳数据)"},
    ],
}


@app.route("/api", methods=["GET"])
def api_index():
    endpoints = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if rule.rule in ("/api", "/health") or rule.rule.startswith("/static"):
            continue
        params = ENDPOINT_PARAMS.get(rule.rule, [])
        endpoints.append({
            "path": rule.rule,
            "methods": sorted(rule.methods - {"OPTIONS", "HEAD"}),
            "params": params,
        })
    return jsonify({"service": "bilibili-mcp-flask", "endpoints": endpoints})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "bilibili-mcp-flask"})


@app.route("/api/video/search", methods=["GET"])
def search_video_api():
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return jsonify({"error": "keyword is required"}), 400

    page = request.args.get("page", default=1, type=int)
    page_size = request.args.get("page_size", default=20, type=int)
    time_start = request.args.get("time_start", default="", type=str)
    time_end = request.args.get("time_end", default="", type=str)
    order_type = request.args.get("order_type", default="totalrank", type=str)

    try:
        data = _run_async(_search_video_async(keyword, page, page_size, time_start, time_end, order_type))
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/video/info/<string:bvid>", methods=["GET"])
def video_info_api(bvid: str):
    try:
        data = _run_async(_get_video_info_async(bvid))
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/video/pbp/<string:bvid>", methods=["GET"])
def video_pbp_api(bvid: str):
    page_index = request.args.get("page_index", type=int)
    cid = request.args.get("cid", type=int)

    try:
        data = _run_async(_get_video_pbp_async(bvid, page_index=page_index, cid=cid))
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/video/subtitle/<string:bvid>", methods=["GET"])
def video_subtitle_api(bvid: str):
    format = request.args.get("format", default="txt", type=str)
    try:
        data = _run_async(_get_video_subtitle_async(bvid, format))
        return jsonify({"bvid": bvid, "subtitle": data})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/media/subtitle", methods=["POST"])
def media_subtitle_api():
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url", "")).strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    format = str(payload.get("format", "txt"))

    try:
        data = _run_async(_get_media_subtitle_async(url, format))
        return jsonify({"url": url, "subtitle": data})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def configure_flask_logging():
    """避免 Flask/Werkzeug access log 被 root logger 重复打印。"""
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    werkzeug_logger.addHandler(handler)

    werkzeug_logger.setLevel(logging.INFO)
    werkzeug_logger.propagate = False


def run_flask_server():
    configure_flask_logging()

    flask_host = os.getenv("FLASK_HOST", "0.0.0.0")
    try:
        flask_port = int(os.getenv("FLASK_PORT", "8001"))
    except ValueError:
        flask_port = 8001

    app.run(host=flask_host, port=flask_port)


if __name__ == "__main__":
    run_flask_server()
