"""
Construye un Chrome WebDriver para entornos Railway/Linux.

Prioridad para el chromedriver:
  1. Paths del sistema (/usr/bin/chromedriver, etc.) — siempre coinciden con
     el Chromium instalado por nixpacks.
  2. webdriver_manager — solo si no hay ninguno en el sistema (dev local).
"""
import os


_CHROME_PATHS = [
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/local/bin/chromium",
]

_CHROMEDRIVER_PATHS = [
    "/usr/bin/chromedriver",
    "/usr/local/bin/chromedriver",
    "/usr/lib/chromium/chromedriver",
    "/usr/lib/chromium-browser/chromedriver",
    "/snap/bin/chromium.chromedriver",
]


def build_chrome_options(headless: bool = True):
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-zygote")
    opts.add_argument("--single-process")
    opts.add_argument("--lang=es-CL,es")
    opts.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    opts.add_experimental_option("useAutomationExtension", False)

    for path in _CHROME_PATHS:
        if os.path.exists(path):
            opts.binary_location = path
            break

    return opts


def _find_chromedriver() -> str | None:
    # 1. Paths fijos del sistema
    for path in _CHROMEDRIVER_PATHS:
        if os.path.exists(path):
            return path
    # 2. Nix store (nixpacks en Railway)
    if os.path.exists("/nix/store"):
        import glob
        nix = glob.glob("/nix/store/*/bin/chromedriver")
        if nix:
            return nix[0]
    # 3. Cualquier chromedriver en PATH
    import shutil
    found = shutil.which("chromedriver")
    if found:
        return found
    return None


def _build_service():
    from selenium.webdriver.chrome.service import Service

    # Preferir chromedriver del sistema (siempre compatible con el Chrome instalado)
    path = _find_chromedriver()
    if path:
        return Service(path)

    # Fallback: webdriver_manager (útil en desarrollo local)
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        return Service(ChromeDriverManager().install())
    except Exception:
        return Service()  # último recurso


def build_driver(headless: bool = True):
    """Devuelve un webdriver.Chrome listo para usar."""
    from selenium import webdriver

    driver = webdriver.Chrome(service=_build_service(), options=build_chrome_options(headless))
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    driver.set_page_load_timeout(30)
    return driver
