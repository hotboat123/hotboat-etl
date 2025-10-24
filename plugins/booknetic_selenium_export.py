import csv
import hashlib
import io
import os
import time
from typing import Any, Dict, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import shutil
import glob


def _best_map(row: Dict[str, Any]) -> Dict[str, Any]:
    def norm(v):
        return v.strip() if isinstance(v, str) else v

    def fk(keys):
        for k in row.keys():
            nk = (k or "").strip().lower().replace(" ", "_")
            for key in keys:
                if key in nk:
                    return k
        return None

    email_k = fk(["email", "correo"]) 
    name_k = fk(["name", "cliente", "customer"]) 
    service_k = fk(["service", "servicio"]) 
    start_k = fk(["start", "fecha", "date", "hora"]) 
    status_k = fk(["status", "estado"]) 
    id_k = fk(["appointment_id", "booking_id", "id"]) 

    mapped = {
        "id": norm(row.get(id_k)) if id_k else None,
        "customer_name": norm(row.get(name_k)) if name_k else None,
        "customer_email": norm(row.get(email_k)) if email_k else None,
        "service_name": norm(row.get(service_k)) if service_k else None,
        "starts_at": norm(row.get(start_k)) if start_k else None,
        "status": norm(row.get(status_k)) if status_k else None,
        "raw": { (k or "").strip().lower().replace(" ", "_"): norm(v) for k, v in row.items() },
    }
    if not mapped["id"]:
        flat = "|".join(f"{k}={v}" for k, v in sorted(mapped["raw"].items()))
        mapped["id"] = hashlib.sha1(flat.encode("utf-8")).hexdigest()
    return mapped


def fetch() -> Dict[str, List[Dict[str, Any]]]:
    """Replicate browser clicks to download CSV from Booknetic UI."""
    base_url = os.getenv("BOOKNETIC_URL") or os.getenv("BOOKNETIC_BASE_URL")
    username = os.getenv("BOOKNETIC_USERNAME")
    password = os.getenv("BOOKNETIC_PASSWORD")
    if not base_url or not username or not password:
        raise RuntimeError("BOOKNETIC_URL/USERNAME/PASSWORD not set for selenium export")

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    prefs = {
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    opts.add_experimental_option("prefs", prefs)

    # Locate Chromium/Chrome binary in Nix or environment
    chrome_bin = (
        os.getenv("CHROME_BIN")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
        or shutil.which("google-chrome")
    )
    if not chrome_bin:
        matches = glob.glob("/nix/store/*chromium*/bin/chromium")
        if matches:
            chrome_bin = matches[0]
    if chrome_bin:
        opts.binary_location = chrome_bin

    if not chrome_bin:
        raise RuntimeError("Chromium/Chrome binary not found; set CHROME_BIN or ensure chromium is installed")

    # Prefer Selenium Manager to resolve chromedriver automatically
    # When CHROME_BIN/binary_location is set, Selenium Manager matches the driver.
    driver = webdriver.Chrome(options=opts)
    wait = WebDriverWait(driver, 20)

    try:
        # Login
        driver.get(base_url.rstrip("/") + "/wp-login.php")
        wait.until(EC.visibility_of_element_located((By.ID, "user_login"))).send_keys(username)
        driver.find_element(By.ID, "user_pass").send_keys(password)
        driver.find_element(By.ID, "wp-submit").click()
        wait.until(EC.url_contains("/wp-admin"))

        # Go to appointments and click Export (Download)
        driver.get(base_url.rstrip("/") + "/wp-admin/admin.php?page=booknetic&module=appointments")
        # Try a few selectors commonly used by Booknetic to export
        selectors = [
            "button[data-action='export']",
            "button.export-csv",
            "a.export-csv",
            "button[onclick*='export']",
            "a[onclick*='export']",
        ]
        clicked = False
        for sel in selectors:
            try:
                el = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
                el.click()
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            # As fallback, try find any element containing 'Export' text
            try:
                el = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(translate(text(),'EXPORT','export'),'export') or contains(@class,'export')]") ))
                el.click()
                clicked = True
            except Exception:
                pass
        if not clicked:
            raise RuntimeError("Export button not found for appointments")

        time.sleep(5)  # allow download to trigger

        # Some installs open a new tab with CSV; try to grab the last response content
        csv_text = None
        try:
            # If a new tab opened with CSV, switch to it and read body text
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
                csv_text = driver.find_element(By.TAG_NAME, "body").text
        except Exception:
            pass

        if not csv_text:
            # Fallback: try to interrogate network is not trivial without CDP; as a last resort, try known direct URL
            import requests
            s = requests.Session()
            # Cookies from selenium to requests
            for c in driver.get_cookies():
                s.cookies.set(c['name'], c['value'])
            url = base_url.rstrip("/") + "/wp-admin/admin.php?page=booknetic&module=appointments&action=export"
            resp = s.get(url, timeout=60)
            resp.raise_for_status()
            csv_text = resp.text

        # Parse CSV
        reader = csv.DictReader(io.StringIO(csv_text))
        appts = [_best_map(r) for r in reader]
        return {"appointments": appts}
    finally:
        driver.quit()


