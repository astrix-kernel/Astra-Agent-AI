"""Browser automation via Playwright — persistent browser instance."""
_pw = None
_browser = None
_page = None
_current_url = [None]


def _ensure():
    global _pw, _browser, _page
    if _browser is not None and _page is not None and not _page.is_closed():
        return _page
    try:
        from playwright.sync_api import sync_playwright
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(
            headless=True, 
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-software-rasterizer',
            ]
        )
        _page = _browser.new_page(
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800},
            locale='en-US',
        )
        
        # === STEALTH: hapus automation flags ===
        _page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            
            window.chrome = { runtime: {} };
            
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        # Coba playwright-stealth kalau ada
        try:
            from playwright_stealth import stealth_sync
            stealth_sync(_page)
            print("[STEALTH] playwright-stealth applied", flush=True)
        except ImportError:
            print("[STEALTH] manual injection only", flush=True)
        except Exception as e:
            print(f"[STEALTH] stealth failed: {e}", flush=True)
        
        return _page
    except Exception as e:
        raise RuntimeError(f"Playwright: {e}")


def browser_open(url):
    """Buka URL, ambil MAIN article content (skip nav/menu)."""
    page = _ensure()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        _current_url[0] = page.url
        title = page.title()
        
        main_selectors = [
            "#mw-content-text",          # Wikipedia
            "article",                    # Semantic
            "main",                       # Semantic
            "[role='main']",              # ARIA
            ".markdown-body",             # GitHub
            ".post-content, .entry-content, .article-content",
            "#content", ".content",
            "body"
        ]
        
        content_text = ""
        used_selector = "body"
        
        for selector in main_selectors:
            try:
                el = page.query_selector(selector)
                if el:
                    text = el.inner_text()
                    if len(text) > 500:
                        content_text = text
                        used_selector = selector
                        break
            except: continue
        
        content_text = "\n".join(line.strip() for line in content_text.split("\n") if line.strip())
        
        if len(content_text) > 5000:
            content_text = content_text[:5000] + "\n...(truncated)"
        
        return f"📄 **{title}**\nURL: {page.url}\nSelector: {used_selector}\n\n{content_text}"
    except Exception as e:
        return f"❌ Error: {e}"


def browser_click(selector):
    """Klik element — wait for navigation kalau ada."""
    page = _ensure()
    try:
        old_url = page.url
        page.click(selector, timeout=15000)
        page.wait_for_timeout(1000)
        
        # Tunggu navigation kalau URL berubah
        if page.url != old_url:
            try:
                page.wait_for_load_state('networkidle', timeout=10000)
            except: pass
            return f"✅ Clicked: {selector}\n→ Navigated to: {page.url}"
        
        return f"✅ Clicked: {selector} (no navigation)"
    except Exception as e:
        return f"❌ Click error: {e}"


def browser_type(selector, text):
    """Isi text ke input — wait longer, try multiple selectors."""
    page = _ensure()
    try:
        # Try wait 15s for selector
        try:
            page.wait_for_selector(selector, timeout=15000, state="visible")
        except:
            # Fallback: try alternative selectors for common sites
            alternatives = [selector]
            if "input[name=q]" in selector:
                alternatives += ["textarea[name=q]", "input[type=text]", "textarea[type=text]", "input[title*='Search']"]
            
            found = False
            for alt in alternatives:
                try:
                    page.wait_for_selector(alt, timeout=3000, state="visible")
                    selector = alt
                    found = True
                    print(f"[TYPE] using alternative: {alt}", flush=True)
                    break
                except: continue
            
            if not found:
                return f"❌ Selector '{selector}' not found after 15s"
        
        # Set realistic user agent (bypass bot detection)
        page.fill(selector, text, timeout=15000)
        page.wait_for_timeout(500)
        return f"✅ Typed '{text[:50]}' into {selector}"
    except Exception as e:
        return f"❌ Type error: {e}"


def browser_press(key):
    """Tekan keyboard (Enter, Tab, Escape, dll)."""
    page = _ensure()
    try:
        page.keyboard.press(key)
        page.wait_for_timeout(300)
        return "✅ Pressed: " + str(key)
    except Exception as e:
        return "❌ Press error: " + str(e)


def browser_wait(seconds=2):
    """Tunggu N detik (buat loading)."""
    page = _ensure()
    try:
        page.wait_for_timeout(int(float(seconds) * 1000))
        return "✅ Waited " + str(seconds) + "s"
    except Exception as e:
        return "❌ Wait error: " + str(e)


def browser_scroll(direction="down", pixels=500):
    """Scroll halaman."""
    page = _ensure()
    try:
        dy = int(pixels) if direction == "down" else -int(pixels)
        page.mouse.wheel(0, dy)
        page.wait_for_timeout(300)
        return "✅ Scrolled " + str(direction) + " " + str(pixels) + "px"
    except Exception as e:
        return "❌ Scroll error: " + str(e)


def browser_fill_form(fields):
    """Fill multiple form fields. fields = dict {selector: value}."""
    page = _ensure()
    results = []
    for selector, value in fields.items():
        try:
            page.fill(selector, value, timeout=5000)
            results.append("✅ " + selector + " = '" + str(value)[:30] + "'")
        except Exception as e:
            results.append("❌ " + selector + ": " + str(e))
    return "\n".join(results)




def browser_screenshot(path="/tmp/astrix_browser.png"):
    """Screenshot halaman."""
    page = _ensure()
    try:
        page.screenshot(path=path, full_page=False)
        return "✅ Screenshot: " + path
    except Exception as e:
        return "❌ Error: " + str(e)


def browser_get_text(selector="body"):
    """Ambil text dari selector tertentu."""
    page = _ensure()
    try:
        text = page.inner_text(selector)[:2000]
        return "📄 Text from '" + selector + "':\n" + text
    except Exception as e:
        return "❌ Error: " + str(e)


def browser_close():
    """Tutup browser."""
    global _pw, _browser, _page
    try:
        if _page: _page.close()
        if _browser: _browser.close()
        if _pw: _pw.stop()
    except: pass
    _pw = _browser = _page = None
    _current_url[0] = None
    return "✅ Browser closed"

BROWSER_TOOLS = {
    "browser_open": browser_open,
    "browser_click": browser_click,
    "browser_type": browser_type,
    "browser_press": browser_press,
    "browser_wait": browser_wait,
    "browser_scroll": browser_scroll,
    "browser_fill_form": browser_fill_form,
    "browser_screenshot": browser_screenshot,
    "browser_get_text": browser_get_text,
    "browser_close": browser_close,
}
