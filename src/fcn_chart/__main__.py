"""啟動服務並開啟瀏覽器：`uv run fcn-chart`。

環境變數：
- APP_PORT：連接埠，預設 8765。
- APP_HOST：綁定位址，預設 127.0.0.1（只限本機）；內網共用時設為 0.0.0.0（見 start-server.bat）。
"""

import os
import socket
import threading
import webbrowser

import uvicorn

LOCALHOST = "127.0.0.1"


def lan_addresses() -> list[str]:
    """本機在區網上的 IPv4 位址（給同事連線用）。"""
    try:
        _, _, addresses = socket.gethostbyname_ex(socket.gethostname())
    except OSError:
        return []
    return [ip for ip in addresses if not ip.startswith("127.")]


def main() -> None:
    host = os.environ.get("APP_HOST", LOCALHOST)
    port = int(os.environ.get("APP_PORT", "8765"))
    local_url = f"http://{LOCALHOST}:{port}/"
    threading.Timer(1.5, webbrowser.open, args=(local_url,)).start()

    print(f"FCN Chart 已啟動：{local_url}（關閉此視窗即可停止）")
    if host != LOCALHOST:
        for ip in lan_addresses():
            print(f"同事請用瀏覽器開啟：http://{ip}:{port}/")
    uvicorn.run("fcn_chart.app:app", host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
