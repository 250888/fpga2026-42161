"""Local-only launcher for the standalone XUNJI workstation. Python 3.8+."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import quote
import webbrowser


def main():
    folder = Path(__file__).resolve().parent
    filename = "瞬迹诊断工作台.html"
    if not (folder / filename).is_file():
        raise FileNotFoundError("Keep the HTML and this launcher in the same folder.")
    handler = partial(SimpleHTTPRequestHandler, directory=str(folder))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    url = "http://127.0.0.1:" + str(server.server_port) + "/" + quote(filename)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    print("XUNJI workstation / local computer only")
    print("Open in Chrome or Edge: " + url)
    print("Keep this window open while using the workstation.")
    webbrowser.open(url)
    try:
        input("Press ENTER to stop the server and exit...\n")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
