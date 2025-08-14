import threading
import time
import webbrowser
import os
from uvicorn import Config, Server
from server import app, get_ipv4_candidates


def open_browser_when_ready(url: str, delay: float = 1.5):
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    # Bind on all interfaces so peers on LAN can connect
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8001))

    # Choose a good LAN URL to open locally in the browser
    ips = get_ipv4_candidates()
    url = f"http://127.0.0.1:{port}"
    if ips:
        url = f"http://{ips[0]}:{port}"

    # Launch default browser shortly after server starts
    threading.Thread(target=open_browser_when_ready, args=(url, 2.0), daemon=True).start()

    # Start server (console/terminal app)
    config = Config(app=app, host=host, port=port, log_level="info")
    server = Server(config)
    server.run()


if __name__ == "__main__":
    main()