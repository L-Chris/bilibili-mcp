import os
import threading

from flask_server import run_flask_server


def run_mcp_server():
    # 延迟导入，避免在 Flask 单独启动时触发 MCP 初始化副作用
    import server

    server.mcp.run(transport=os.getenv("MCP_TRANSPORT", "stdio"))


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()

    run_mcp_server()
