"""Screenshot the running QCM viewer for visual QA.

Boots `panel serve` on a free port, drives a headless Chromium through the three
pages (Data / Results / Export) + the raw-sweep drawer, and writes PNGs to
/tmp/qcm_shots/. Run from the project root with the venv active:

    python tools/shoot.py [run-dir ...]

Hard-won subprocess rules (violating them makes the server look "hung"):

- NEVER pipe the server's stdout to a PIPE you don't drain — Bokeh logs enough
  per session to fill the 64 KB pipe buffer and block the whole server.
- NEVER retry ``page.goto`` with a short timeout — every aborted request
  spawns a fresh server session whose document build (~15 s for a multi-run
  workspace) keeps running, piling up until nothing finishes. Wait for the
  port, then issue ONE goto with a generous timeout.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/tmp/qcm_shots")
OUT.mkdir(exist_ok=True)
SERVER_LOG = Path("/tmp/qcm_shoot_server.log")
VIEW = (1440, 900)
PAGE_CLASSES = {"Results": ".qcm-page-results", "Export": ".qcm-page-report"}


def free_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main(run_dirs: list[str]) -> None:
    port = free_port()
    with SERVER_LOG.open("w") as log:
        proc = subprocess.Popen(
            ["python", "-m", "panel", "serve", "qcm/panel_app.py",
             "--port", str(port), "--args", *run_dirs],
            stdout=log, stderr=subprocess.STDOUT,
        )
        url = f"http://localhost:{port}/panel_app"
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="chrome")
                page = browser.new_page(viewport={"width": VIEW[0], "height": VIEW[1]})
                for _ in range(120):  # wait for the port, not the page
                    try:
                        socket.create_connection(("localhost", port), timeout=1).close()
                        break
                    except OSError:
                        time.sleep(0.5)
                page.goto(url, wait_until="domcontentloaded", timeout=240000)
                page.wait_for_selector(".qcm-brand", timeout=120000)
                page.wait_for_timeout(6000)

                def shot(name: str) -> None:
                    page.wait_for_timeout(2000)
                    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True,
                                    timeout=60000)
                    print("wrote", OUT / f"{name}.png")

                shot("01-data")
                for label, name in [("Results", "02-results"), ("Export", "03-report")]:
                    try:
                        page.get_by_text(label, exact=False).first.click(timeout=5000)
                        page.wait_for_selector(PAGE_CLASSES[label], timeout=120000)
                        page.wait_for_timeout(4000)
                        shot(name)
                    except Exception as e:  # noqa: BLE001
                        print("nav", label, "failed:", e)

                try:
                    page.get_by_text("Data", exact=False).first.click(timeout=5000)
                    page.wait_for_timeout(2000)
                    page.get_by_text("Inspect raw sweeps", exact=False).first.click(timeout=5000)
                    page.wait_for_timeout(3000)
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
    main(sys.argv[1:] or ["./view-run"])
