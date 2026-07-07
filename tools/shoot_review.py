"""Legible, scrolled viewport frames of every page for a detailed design review."""
from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/tmp/qcm_review")
OUT.mkdir(exist_ok=True)
W, H = 1440, 900


def free_port() -> int:
    s = socket.socket(); s.bind(("", 0)); p = s.getsockname()[1]; s.close(); return p


def main() -> None:
    port = free_port()
    proc = subprocess.Popen(
        ["python", "-m", "panel", "serve", "qcm/panel_app.py", "--port", str(port), "--args", "./view-run"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    url = f"http://localhost:{port}/panel_app"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome")
            page = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
            for _ in range(60):
                try:
                    page.goto(url, wait_until="networkidle", timeout=3000); break
                except Exception:
                    time.sleep(0.5)
            page.wait_for_timeout(3500)

            def frames(prefix: str, n: int) -> None:
                page.evaluate("window.scrollTo(0,0)")
                page.wait_for_timeout(400)
                for i in range(n):
                    page.wait_for_timeout(600)
                    page.screenshot(path=str(OUT / f"{prefix}-{i}.png"))
                    page.evaluate(f"window.scrollTo(0,{(i+1)*820})")
                print("frames", prefix, n)

            frames("data", 2)
            page.get_by_text("Results", exact=False).first.click(timeout=4000)
            page.wait_for_timeout(2500); frames("results", 3)
            page.get_by_text("Report", exact=False).first.click(timeout=4000)
            page.wait_for_timeout(2000); frames("report", 2)
            # drawer: back to data, open it
            page.get_by_text("Data", exact=False).first.click(timeout=4000)
            page.wait_for_timeout(800)
            try:
                page.get_by_role("button", name="Inspect raw sweeps").click(timeout=4000)
            except Exception:
                page.get_by_text("Inspect raw sweeps", exact=False).first.click(timeout=4000)
            page.wait_for_timeout(2500)
            page.screenshot(path=str(OUT / "drawer-0.png"))
            print("frames drawer 1")
            b.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
