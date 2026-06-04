"""Exercise the QCM viewer's features and capture errors + state screenshots.

Drives a headless Chrome through the main interactions on each page, records
browser console errors / page exceptions, and screenshots key states. Combined
with the panel server log (grep for Traceback), this tells us what actually
works vs. silently fails.
"""
from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/tmp/qcm_eval")
OUT.mkdir(exist_ok=True)
LOG = OUT / "server.log"


def free_port() -> int:
    s = socket.socket(); s.bind(("", 0)); p = s.getsockname()[1]; s.close(); return p


def main() -> None:
    port = free_port()
    logf = open(LOG, "w")
    proc = subprocess.Popen(
        ["python", "-m", "panel", "serve", "qcm/panel_app.py", "--port", str(port), "--args", "./view-run"],
        stdout=logf, stderr=subprocess.STDOUT,
    )
    url = f"http://localhost:{port}/panel_app"
    console_errors: list[str] = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome")
            page = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            page.on("console", lambda m: console_errors.append(f"{m.type}: {m.text}") if m.type in ("error",) else None)
            page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))
            for _ in range(60):
                try:
                    page.goto(url, wait_until="networkidle", timeout=3000); break
                except Exception:
                    time.sleep(0.5)
            page.wait_for_timeout(4000)

            log: list[str] = []

            def step(desc: str, fn) -> None:
                before = len(console_errors)
                try:
                    fn()
                    page.wait_for_timeout(900)
                    ok = "ok"
                except Exception as e:  # noqa: BLE001
                    ok = f"FAILED interaction: {e}"
                new_err = console_errors[before:]
                log.append(f"[{desc}] {ok}" + (f" | console: {new_err}" if new_err else ""))

            def click_text(t, exact=False):
                page.get_by_text(t, exact=exact).first.click(timeout=4000)

            def shot(name):
                page.screenshot(path=str(OUT / f"{name}.png"))

            # ---- DATA page interactions
            step("data: toggle y=0 line", lambda: click_text("y = 0 line"))
            step("data: toggle Show cycles", lambda: click_text("Show cycles"))
            step("data: selection mode Reference range", lambda: click_text("Reference range"))
            step("data: selection mode Mark range", lambda: click_text("Mark range"))
            step("data: selection mode Analysis range", lambda: click_text("Analysis range"))
            step("data: Full range button", lambda: click_text("Full range"))
            shot("data-after-toggles")
            # x-axis / y-axis selects (native <select> inside Panel)
            def set_select(label_value):
                # find selects on page; choose by visible option label
                sels = page.locator("select")
                return sels
            step("data: change X-axis select", lambda: page.locator("select").first.select_option(label="Potential"))
            shot("data-xaxis-potential")
            step("data: reset X-axis to Time", lambda: page.locator("select").first.select_option(label="Time"))

            # signals checkboxes (toggle first ΔD checkbox off/on)
            step("data: toggle a signal checkbox", lambda: page.locator("input[type=checkbox]").nth(4).click())
            # expand Edit phases
            step("data: expand Edit phases", lambda: click_text("Edit phases"))
            shot("data-edit-phases")

            # drawer
            step("data: open drawer", lambda: page.get_by_role("button", name="Inspect raw sweeps").click())
            page.wait_for_timeout(1500)
            shot("drawer-open")
            step("drawer: Next sweep", lambda: click_text("Next"))
            step("drawer: One channel toggle", lambda: click_text("One channel"))
            shot("drawer-one-channel")
            step("drawer: Reset plot scale", lambda: click_text("Reset plot scale"))
            step("drawer: close", lambda: page.get_by_role("button", name="Close").click())
            page.wait_for_timeout(800)

            # ---- RESULTS page
            step("nav: Results", lambda: click_text("Results"))
            page.wait_for_timeout(1500)
            step("results: technique CV", lambda: click_text("CV", exact=True))
            step("results: technique CP", lambda: click_text("CP", exact=True))
            step("results: technique Auto", lambda: click_text("Auto", exact=True))
            step("results: cycle Single", lambda: click_text("Single", exact=True))
            step("results: cycle Range", lambda: click_text("Range", exact=True))
            step("results: cycle All", lambda: click_text("All", exact=True))
            shot("results-after")

            # ---- REPORT page
            step("nav: Report", lambda: click_text("Report"))
            page.wait_for_timeout(1500)
            step("report: uncheck Plots", lambda: click_text("Plots"))
            step("report: change export format", lambda: page.locator("select").last.select_option(index=1))
            shot("report-after")

            b.close()
            print("\n".join(log))
            print("\n=== CONSOLE ERRORS (", len(console_errors), ") ===")
            for e in console_errors[:40]:
                print(e)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        logf.close()


if __name__ == "__main__":
    main()
