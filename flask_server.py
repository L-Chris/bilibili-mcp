import asyncio
import os
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


async def _search_video_async(keyword: str, page: int = 1, page_size: int = 20) -> dict:
    search_result = await search.search_by_type(
        keyword,
        search_type=search.SearchObjectType.VIDEO,
        page=page,
        page_size=page_size,
    )

    items = []

    for item in search_result.get("result", []):
        # 打印item
        item['pubdate'] = datetime.fromtimestamp(item["pubdate"]).strftime("%Y/%m/%d")
        items.append(item)

    return {
        "keyword": keyword,
        "page": page,
        "page_size": page_size,
        "total": len(items),
        "items": items,
    }


async def _get_video_subtitle_async(bvid: str):
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

        asr_data = await get_audio_subtitle_async(audio_url)
        return asr_data

    subtitle_url = target_subtitle["subtitle_url"]
    if not subtitle_url.startswith(("http://", "https://")):
        subtitle_url = f"https:{subtitle_url}"

    async with aiohttp.ClientSession() as session:
        async with session.get(subtitle_url) as response:
            subtitle_content = await response.json()
            if "body" in subtitle_content:
                subtitle_text = "".join(item["content"] for item in subtitle_content["body"])
                return subtitle_text
            return subtitle_content


async def _get_video_info_async(bvid: str) -> dict:
    v = video.Video(bvid=bvid, credential=credential)
    return await v.get_info()


async def _get_media_subtitle_async(url: str):
    return await get_audio_subtitle_async(url)


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

    try:
        data = _run_async(_search_video_async(keyword, page, page_size))
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


@app.route("/api/video/subtitle/<string:bvid>", methods=["GET"])
def video_subtitle_api(bvid: str):
    try:
        data = _run_async(_get_video_subtitle_async(bvid))
        return jsonify({"bvid": bvid, "subtitle": data})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/media/subtitle", methods=["POST"])
def media_subtitle_api():
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url", "")).strip()
    if not url:
        return jsonify({"error": "url is required"}), 400

    try:
        data = _run_async(_get_media_subtitle_async(url))
        return jsonify({"url": url, "subtitle": data})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def run_flask_server():
    flask_host = os.getenv("FLASK_HOST", "0.0.0.0")
    try:
        flask_port = int(os.getenv("FLASK_PORT", "8001"))
    except ValueError:
        flask_port = 8001

    app.run(host=flask_host, port=flask_port)


if __name__ == "__main__":
    run_flask_server()
