"""啟動本機服務並開啟瀏覽器：`uv run fcn-chart`。"""

import os
import threading
import webbrowser

import uvicorn

HOST = "127.0.0.1"


def main() -> None:
    port = int(os.environ.get("APP_PORT", "8765"))
    url = f"http://{HOST}:{port}/"
    threading.Timer(1.5, webbrowser.open, args=(url,)).start()
    print(f"FCN Chart 已啟動：{url}（關閉此視窗即可停止）")
    uvicorn.run("fcn_chart.app:app", host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
