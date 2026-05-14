#!/usr/bin/env python3
"""直接测试字幕相关代码方法（不经过 HTTP API）。

用法:
    # 测试视频字幕（默认 BV ID，txt 格式）
    python test_subtitle_api.py

    # 指定 BV ID 和格式
    python test_subtitle_api.py --bvid BV1xx4y1K7kF --format srt

    # 测试所有格式
    python test_subtitle_api.py --bvid BV1xx4y1K7kF --all

    # 测试媒体音频字幕（BcutASR）
    python test_subtitle_api.py --media-url "https://xxx.audio.m4s"

    # 跳过视频字幕，只测音频
    python test_subtitle_api.py --skip-video --media-url "https://xxx.audio.m4s"
"""

import argparse
import asyncio
import json
import sys
import time


def test_video_subtitle(bvid: str, fmt: str = "txt"):
    """直接调用 _get_video_subtitle_async"""
    from flask_server import _get_video_subtitle_async

    label = {"txt": "纯文本", "srt": "SRT时间戳", "raw": "原始数据"}
    print(f"\n{'='*60}")
    print(f"[视频字幕] BV={bvid}  format={fmt} ({label.get(fmt, fmt)})")
    print(f"{'='*60}")

    t0 = time.time()
    result = None
    try:
        result = asyncio.run(_get_video_subtitle_async(bvid, fmt))
    except Exception as e:
        print(f"ERROR: {e}")
        return None
    elapsed = time.time() - t0

    _print_subtitle_result(result, fmt, elapsed)
    return result


def test_media_subtitle(audio_url: str, fmt: str = "txt"):
    """直接调用 get_audio_subtitle（BcutASR）"""
    from bcut_asr import get_audio_subtitle

    label = {"txt": "纯文本", "srt": "SRT时间戳", "raw": "原始数据"}
    print(f"\n{'='*60}")
    print(f"[媒体字幕] URL={audio_url[:80]}...  format={fmt} ({label.get(fmt, fmt)})")
    print(f"{'='*60}")

    t0 = time.time()
    try:
        result = get_audio_subtitle(audio_url, fmt)
    except Exception as e:
        print(f"ERROR: {e}")
        return None
    elapsed = time.time() - t0

    _print_subtitle_result(result, fmt, elapsed)
    return result


def _print_subtitle_result(result, fmt, elapsed):
    if result is None:
        return

    if fmt == "raw":
        if isinstance(result, list):
            print(f"分段数: {len(result)}  耗时: {elapsed:.1f}s")
            print(f"\n前 3 段:")
            for seg in result[:3]:
                content = seg.get("content", "")[:120]
                print(f"  [{seg.get('from', 0):.1f}s - {seg.get('to', 0):.1f}s] {content}")
            if len(result) > 3:
                print(f"  ... 省略 {len(result) - 3} 段")
            if len(result) >= 3:
                print(f"\n后 3 段:")
                for seg in result[-3:]:
                    content = seg.get("content", "")[:120]
                    print(f"  [{seg.get('from', 0):.1f}s - {seg.get('to', 0):.1f}s] {content}")
        else:
            print(f"返回类型: {type(result).__name__}")
            dumped = json.dumps(result, ensure_ascii=False, indent=2)
            print(dumped[:800])
    else:
        text = result if isinstance(result, str) else str(result)
        lines = text.count("\n")
        print(f"字符数: {len(text)}  行数: ~{lines}  耗时: {elapsed:.1f}s")
        print(f"\n--- 前 500 字符 ---")
        print(text[:500])
        if len(text) > 500:
            print(f"... (省略 {len(text) - 500} 字符)")
        if fmt == "srt":
            # 也显示最后几条字幕
            print(f"\n--- 最后 3 条字幕 ---")
            entries = text.strip().split("\n\n")
            for entry in entries[-3:]:
                print(entry[:200])
                print()


def main():
    parser = argparse.ArgumentParser(
        description="直接测试字幕代码方法",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--bvid", default="BV1GJ4m1K7qa", help="视频 BV ID")
    parser.add_argument("--format", "-f", default="txt", choices=["txt", "srt", "raw"])
    parser.add_argument("--all", "-a", action="store_true", help="测试全部三种格式")
    parser.add_argument("--media-url", "-m", default=None, help="音频 URL（测试 BcutASR）")
    parser.add_argument("--skip-video", action="store_true", help="跳过视频字幕测试")

    args = parser.parse_args()

    if not args.skip_video:
        if args.all:
            for fmt in ("txt", "srt", "raw"):
                result = test_video_subtitle(args.bvid, fmt)
                if isinstance(result, str) and result == "没有找到AI生成的中文字幕":
                    print("(无 AI 字幕，已通过 BcutASR 回退生成)")
        else:
            test_video_subtitle(args.bvid, args.format)

    if args.media_url:
        test_media_subtitle(args.media_url, args.format)

    print(f"\n{'='*60}")
    print("测试完成")


if __name__ == "__main__":
    main()
