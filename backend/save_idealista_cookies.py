"""
Run this script once to save your Idealista session cookies.

    cd backend
    python save_idealista_cookies.py

A Chrome window will open on idealista.com. Log in (email/password or Google),
then come back here and press Enter. The session cookies are saved to
idealista_cookies.json and will be reused automatically by the scraper
when IDEALISTA_USE_PROFILE=true.
"""

import json
import os
import subprocess
import sys
import time


def _chrome_major_version() -> int | None:
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in paths:
        try:
            out = subprocess.check_output(
                ["powershell", "-command", f"(Get-Item '{path}').VersionInfo.ProductMajorPart"],
                timeout=5,
            )
            return int(out.strip())
        except Exception:
            continue
    return None


def main() -> None:
    try:
        import undetected_chromedriver as uc
    except ImportError:
        print("ERROR: undetected-chromedriver not installed.")
        print("Run: pip install undetected-chromedriver setuptools")
        sys.exit(1)

    out_path = os.path.join(os.path.dirname(__file__), "idealista_cookies.json")
    chrome_version = _chrome_major_version()

    options = uc.ChromeOptions()
    options.add_argument("--lang=es-ES")
    options.add_argument("--window-size=1200,800")

    kwargs: dict = {"options": options, "headless": False, "use_subprocess": True}
    if chrome_version:
        kwargs["version_main"] = chrome_version

    print("Opening Chrome… (this may take a few seconds)")
    driver = uc.Chrome(**kwargs)

    try:
        driver.get("https://www.idealista.com/acceso/entrar")
        time.sleep(3)

        print()
        print("=" * 60)
        print("  Log in to Idealista in the Chrome window that just opened.")
        print("  You can use email/password or 'Continuar con Google'.")
        print("  Once you are logged in, come back here and press Enter.")
        print("=" * 60)
        input("\n  Press Enter when you are logged in... ")

        # Give the page a moment to settle after login
        time.sleep(2)

        raw_cookies = driver.get_cookies()
        idealista_cookies = [
            c for c in raw_cookies if "idealista" in c.get("domain", "")
        ]

        if not idealista_cookies:
            print("\nWARNING: No Idealista cookies found. Are you sure you logged in?")
        else:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(idealista_cookies, f, ensure_ascii=False, indent=2)
            print(f"\nSaved {len(idealista_cookies)} cookies to {out_path}")
            print("The scraper will use these automatically when IDEALISTA_USE_PROFILE=true.")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
