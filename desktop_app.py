from pathlib import Path
from tkinter import Tk, filedialog, messagebox
import threading
import time
import urllib.request

import panel as pn
import webview

from qcm.viz.app import QCMViewer


PORT = 5007
URL = f"http://127.0.0.1:{PORT}"


def choose_run():
    root = Tk()
    root.withdraw()

    default = Path(__file__).parent / "view-run"

    if (default / "manifest.json").exists():
        return str(default)

    while True:
        selected = filedialog.askdirectory(
            title="Select QCM run folder containing manifest.json"
        )

        if not selected:
            return None

        selected = Path(selected)

        if (selected / "manifest.json").exists():
            return str(selected)

        messagebox.showerror(
            "Invalid QCM run folder",
            f"That folder does not contain manifest.json:\n\n{selected}"
        )


def serve(run_path):
    viewer = QCMViewer(run_path)

    pn.serve(
        viewer.view(),
        port=PORT,
        address="127.0.0.1",
        show=False,
        websocket_origin=[
            f"127.0.0.1:{PORT}",
            f"localhost:{PORT}",
        ],
    )


def wait_for_server():
    for _ in range(200):
        try:
            urllib.request.urlopen(URL, timeout=0.25)
            return
        except Exception:
            time.sleep(0.1)

    raise RuntimeError("Panel server did not start.")


if __name__ == "__main__":
    run_path = choose_run()

    if not run_path:
        raise SystemExit("No run selected")

    thread = threading.Thread(
        target=serve,
        args=(run_path,),
        daemon=True,
    )
    thread.start()

    wait_for_server()

    webview.create_window(
        "QCM Analysis Workbench",
        URL,
        width=1600,
        height=1000,
    )

    webview.start(debug=True)