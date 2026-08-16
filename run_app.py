import os
import sys
import webbrowser
import threading
import time
import streamlit.web.cli as stcli

def resolve_path(path):
    """Resolves relative paths whether running as a script or compiled exe."""
    if getattr(sys, "frozen", False):
        basedir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        basedir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(basedir, path)

def open_browser():
    """Waits for the Streamlit server to spin up and opens the browser."""
    time.sleep(2)
    webbrowser.open_new("http://127.0.0.1:8501")

if __name__ == "__main__":
    app_path = resolve_path("web_app.py")
    threading.Thread(target=open_browser, daemon=True).start()
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.address=127.0.0.1",
        "--server.port=8501",
        "--global.developmentMode=false",
        "--server.headless=true"
    ]
    sys.exit(stcli.main())