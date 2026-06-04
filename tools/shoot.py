"""Screenshot the running QCM viewer for visual QA.

Boots `panel serve` on a free port, drives a headless Chromium through the three
pages (Data / Results / Report) + the raw-sweep drawer, and writes PNGs to
/tmp/qcm_shots/. Run from the project root with the venv active:

    python tools/shoot.py
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/tmp/qcm_shots")
OUT.mkdir(exist_ok=True)
RUN = "./view-run"
VIEW = (1440, 900)


def free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main() -> None:
    port = free_port()
    proc = subprocess.Popen(
        ["python", "-m", "panel", "serve", "qcm/panel_app.py", "--port", str(port), "--args", RUN],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    url = f"http://localhost:{port}/panel_app"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome")
            page = browser.new_page(viewport={"width": VIEW[0], "height": VIEW[1]})
            # wait for server
            for _ in range(60):
                try:
                    page.goto(url, wait_until="networkidle", timeout=3000)
                    break
                except Exception:
                    time.sleep(0.5)
            # let Bokeh finish laying out
            page.wait_for_timeout(3500)

            def shot(name: str) -> None:
                page.wait_for_timeout(1200)
                page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
                print("wrote", OUT / f"{name}.png")

            shot("01-data")

            # nav: Results, Report (sidebar nav buttons carry the label text)
            for label, name in [("Results", "02-results"), ("Report", "03-report")]:
                try:
                    page.get_by_text(label, exact=False).first.click(timeout=4000)
                    shot(name)
                except Exception as e:  # noqa: BLE001
                    print("nav", label, "failed:", e)

            # back to data, open the raw-sweep drawer
            try:
                page.get_by_text("Data", exact=False).first.click(timeout=4000)
                page.wait_for_timeout(800)
                page.get_by_text("Inspect raw sweeps", exact=False).first.click(timeout=4000)
                shot("04-drawer")
            except Exception as e:  # noqa: BLE001
                print("drawer failed:", e)

            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
