# Bilibili MCP 服务器

[English](README.en.md) | [中文](README.md)

这个MCP服务器提供了搜索和交互B站（哔哩哔哩）内容的功能，包括视频搜索、字幕获取和视频信息查询等。

现在同时提供两种服务：
- MCP 服务（默认 `8000`，SSE/stdio）
- Flask REST API 服务（默认 `8001`）

## 功能特点

- 搜索B站视频
- 获取视频字幕（自动生成的AI字幕）
- 查询视频详细信息
- 使用必剪API获取媒体文件的AI字幕

## 组件

### 工具

- **search_video**
  - 从B站搜索视频，支持按发布时间范围和排序方式筛选
  - 输入:
    - `keyword` (string): 搜索关键词
    - `page` (int, 可选): 页码，默认1
    - `page_size` (int, 可选): 每页数量，默认20
    - `time_start` (string, 可选): 发布时间起始，格式 YYYY-MM-DD
    - `time_end` (string, 可选): 发布时间截止，格式 YYYY-MM-DD
    - `order_type` (string, 可选): 排序方式，可选 totalrank(综合)/click(播放量)/pubdate(发布时间)/dm(弹幕)/stow(收藏)/scores(评论)，默认 totalrank

- **get_video_subtitle**
  - 获取B站视频的字幕
  - 输入:
    - `bvid` (string): 视频的BV号
    - `format` (string, 可选): 字幕格式，可选 txt(纯文本，默认)/srt(带时间戳)/raw(原始时间戳数据)

- **get_video_info**
  - 获取B站视频的详细信息
  - 输入:
    - `bvid` (string): 视频的BV号

- **get_media_subtitle**
  - 使用必剪API获取媒体文件的AI中文字幕
  - 输入:
    - `url` (string): 媒体文件URL
    - `format` (string, 可选): 字幕格式，同上

## 开始使用

1. 克隆仓库
2. 安装依赖: `pip install -r requirements.txt`
3. 设置环境变量（从B站官网cookie获取）:
   - `sessdata`: B站SESSDATA
   - `bili_jct`: B站bili_jct
   - `buvid3`: B站buvid3
4. 启动服务器: `python server.py`

如需同时启动 MCP + Flask REST API：

```bash
python run_servers.py
```

### Flask REST API

- `GET /api` — 返回所有可用接口及其参数说明
- `GET /health`
- `GET /api/video/search?keyword=关键词&page=1&page_size=20&time_start=2024-01-01&time_end=2024-06-30&order_type=pubdate`
- `GET /api/video/info/<bvid>`
- `GET /api/video/pbp/<bvid>?page_index=0`
- `GET /api/video/subtitle/<bvid>?format=txt`
- `POST /api/media/subtitle`，JSON body: `{ "url": "媒体地址", "format": "txt" }`

### 与桌面应用集成

要将此服务器与桌面应用集成，请在应用的服务器配置中添加以下内容:

```json
{
  "mcpServers": {
    "bilibili-mcp": {
      "command": "python",
      "args": [
        "{绝对路径}/server.py"
      ],
      "env": {
        "sessdata": "你的B站SESSDATA",
        "bili_jct": "你的B站bili_jct",
        "buvid3": "你的B站buvid3"
      }
    }
  }
}
```

## 开发

- 安装依赖: `pip install -r requirements.txt`
- 启动服务器: `python server.py`
- 同时启动 MCP + Flask: `python run_servers.py`

## 依赖项

- [mcp](https://github.com/modelcontextprotocol/sdk): MCP SDK
- [bilibili-api-python](https://github.com/Nemo2011/bilibili-api): B站API Python库
- [aiohttp](https://docs.aiohttp.org/): 异步HTTP客户端/服务器框架
- [brotlicffi](https://github.com/python-hyper/brotlicffi): Brotli 压缩解码支持（修复 aiohttp 3.13+ 与 B站 API 的 `br` 内容编码兼容问题）

## 资源

- [B站API文档](https://github.com/SocialSisterYi/bilibili-API-collect)
- [必剪API](https://www.bilibili.com/read/cv12349604/)

## 更新日志

### 最新变更

**修复 Brotli 解码错误**
- 新增 `brotlicffi` 依赖，修复 aiohttp 3.13+ 无法解码 B站返回的 `Content-Encoding: br` 响应的问题，影响所有工具（`search_video`、`get_video_info`、`get_video_subtitle`）

**字幕获取优化（PR #1 by [@Zhao-zzzzZ](https://github.com/Zhao-zzzzZ)）**
- 修复 `get_video_subtitle`：字幕列表获取改用 `.get()` 安全访问，避免视频无字幕时崩溃
- 修复 AI 字幕语言匹配条件，放宽为只需 `lan == "ai-zh"`，兼容更多视频
- 异步化音频字幕获取：`get_audio_subtitle` 改为通过 `asyncio.to_thread` 包装为异步，避免阻塞事件循环
- 修复错误处理：`get_audio_subtitle` 将错误由返回值改为正确抛出 `APIError` 异常
- 修复 `ResultRspSchema` 模型：`result` 和 `remark` 字段改为可选，避免解析失败
- 补全 `requirements.txt` 缺失的 `requests`、`pydantic`、`tabulate` 依赖
- 支持音频格式扩展至 mp4/m4s，改进音频 URL 选择策略

## 许可证

本项目采用MIT许可证。