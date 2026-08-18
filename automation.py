from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

import time
import os
import concurrent.futures
import threading


# ============================================================
# BROWSER CLEANUP
# ============================================================

def safe_quit(browser):
    def close():
        try:
            browser.close()
        except Exception:
            pass

    threading.Thread(target=close, daemon=True).start()


# ============================================================
# DEBUG
# ============================================================

def save_debug(page, debug_dir, name, num):
    os.makedirs(debug_dir, exist_ok=True)

    screenshot = os.path.join(
        debug_dir,
        f"{name}_{num}.png"
    )

    html = os.path.join(
        debug_dir,
        f"{name}_{num}.html"
    )

    try:
        page.screenshot(
            path=screenshot,
            full_page=True
        )

        with open(
            html,
            "w",
            encoding="utf-8"
        ) as file:
            file.write(page.content())

        print(f"   📸 Screenshot: {screenshot}")
        print(f"   📄 HTML: {html}")

    except Exception as error:
        print(
            f"   ⚠️ Could not save debug files: {error}"
        )


# ============================================================
# CLOUDFLARE DETECTION
# ============================================================

def is_cloudflare_page(page):
    try:
        title = (page.title() or "").lower()
        source = page.content().lower()

        indicators = [
            "attention required",
            "cloudflare",
            "cf-chl-",
            "challenge-platform",
            "verify you are human",
        ]

        return any(
            indicator in title or indicator in source
            for indicator in indicators
        )

    except Exception:
        return False


# ============================================================
# LOGIN SELECTORS
# ============================================================

MOBILE_SELECTORS = [
    "input[type='tel']",

    "input[name*='mobile' i]",
    "input[name*='phone' i]",
    "input[name*='number' i]",

    "input[id*='mobile' i]",
    "input[id*='phone' i]",
    "input[id*='number' i]",

    "input[placeholder*='mobile' i]",
    "input[placeholder*='phone' i]",
    "input[placeholder*='number' i]",

    "input[autocomplete='tel']",
]


PASSWORD_SELECTORS = [
    "input[type='password']",
    "input[name*='password' i]",
    "input[id*='password' i]",
    "input[placeholder*='password' i]",
]


LOGIN_SELECTORS = [
    "button:has-text('Login')",
    "button:has-text('Log in')",
    "button:has-text('Sign in')",
    "button[type='submit']",
    "input[type='submit']",
]


DAILY_COIN_SELECTORS = [
    "button:has-text('Daily coins')",
    "[role='button']:has-text('Daily coins')",
    "a:has-text('Daily coins')",
    "button:has-text('Daily coin')",
    "a:has-text('Daily coin')",
]


SIGN_IN_SELECTORS = [
    "button:has-text('Sign in')",
    "[role='button']:has-text('Sign in')",
    "a:has-text('Sign in')",
]


# ============================================================
# FIND ELEMENT
# ============================================================

def find_element(page, selectors, timeout=15):
    end_time = time.time() + timeout

    while time.time() < end_time:

        for selector in selectors:

            try:
                locator = page.locator(selector).first

                if locator.is_visible() and locator.is_enabled():
                    return locator

            except Exception:
                continue

        time.sleep(0.5)

    return None


# ============================================================
# CLICK HELPER
# ============================================================

def robust_click(page, element):

    try:
        element.click()
        return True

    except Exception:
        pass

    try:
        element.scroll_into_view_if_needed()
        time.sleep(0.3)
        element.click(force=True)
        return True

    except Exception:
        return False


# ============================================================
# PROCESS ONE NUMBER
# ============================================================

def process_one_number(page, target_url, num, debug_dir):

    print(f"   🌐 Opening: {target_url}")

    try:
        page.goto(
            target_url,
            wait_until="domcontentloaded",
            timeout=35000
        )

    except PlaywrightTimeoutError:
        print("   ⚠️ Page load timed out; checking current page...")

    time.sleep(5)

    print(f"   🌐 Current URL: {page.url}")
    print(f"   📄 Page title: {page.title()}")

    # --------------------------------------------------------
    # CLOUDFLARE
    # --------------------------------------------------------

    if is_cloudflare_page(page):

        save_debug(
            page,
            debug_dir,
            "cloudflare_blocked",
            num
        )

        raise PlaywrightTimeoutError(
            "Cloudflare page detected. "
            "The actual login page was not loaded."
        )

    # --------------------------------------------------------
    # MOBILE
    # --------------------------------------------------------

    print(
        "   🔎 Looking for mobile/number input..."
    )

    mobile = find_element(
        page,
        MOBILE_SELECTORS,
        timeout=15
    )

    if mobile is None:

        save_debug(
            page,
            debug_dir,
            "mobile_input_not_found",
            num
        )

        raise PlaywrightTimeoutError(
            "Could not find mobile/number input."
        )

    mobile.fill(num)

    print(
        f"   📱 Number entered: {num}"
    )

    # --------------------------------------------------------
    # PASSWORD
    # --------------------------------------------------------

    print(
        "   🔎 Looking for password input..."
    )

    password = find_element(
        page,
        PASSWORD_SELECTORS,
        timeout=15
    )

    if password is None:

        save_debug(
            page,
            debug_dir,
            "password_input_not_found",
            num
        )

        raise PlaywrightTimeoutError(
            "Could not find password input."
        )

    password.fill(num)

    print(
        "   🔑 Password entered"
    )

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    print(
        "   🔎 Looking for Login button..."
    )

    login_btn = find_element(
        page,
        LOGIN_SELECTORS,
        timeout=15
    )

    if login_btn is None:

        save_debug(
            page,
            debug_dir,
            "login_button_not_found",
            num
        )

        raise PlaywrightTimeoutError(
            "Could not find Login button."
        )

    if not robust_click(page, login_btn):

        raise Exception(
            "Could not click Login button."
        )

    print(
        "   ✅ Login clicked"
    )

    time.sleep(7)

    # --------------------------------------------------------
    # DAILY COINS
    # --------------------------------------------------------

    print(
        "   🔎 Looking for 'Daily coins' button..."
    )

    daily_btn = find_element(
        page,
        DAILY_COIN_SELECTORS,
        timeout=15
    )

    if daily_btn is None:

        save_debug(
            page,
            debug_dir,
            "daily_coin_not_found",
            num
        )

        raise PlaywrightTimeoutError(
            "Could not find Daily Coins button."
        )

    if not robust_click(page, daily_btn):

        raise Exception(
            "Could not click Daily Coins button."
        )

    print(
        "   ✅ Clicked 'Daily coins'!"
    )

    time.sleep(4)

    # --------------------------------------------------------
    # SIGN IN
    # --------------------------------------------------------

    print(
        "   🔎 Looking for 'Sign In' button..."
    )

    sign_btn = find_element(
        page,
        SIGN_IN_SELECTORS,
        timeout=15
    )

    if sign_btn is None:

        save_debug(
            page,
            debug_dir,
            "sign_in_not_found",
            num
        )

        raise PlaywrightTimeoutError(
            "Could not find Sign In button."
        )

    if not robust_click(page, sign_btn):

        raise Exception(
            "Could not click Sign In button."
        )

    print(
        "   ✅ Clicked Sign In!")


# ============================================================
# START PLAYWRIGHT
# ============================================================

def start_browser(playwright):
    browser = playwright.chromium.launch(
        headless=True
    )


    context = browser.new_context(
        viewport={
            "width": 1280,
            "height": 900
        }
    )

    page = context.new_page()

    page.set_default_timeout(15000)

    return browser, context, page


# ============================================================
# MAIN AUTOMATION
# ============================================================

def run_automation(
    target_url,
    numbers_file,
    stop_event=None
):

    browser = None
    context = None
    page = None

    debug_dir = "debug_output"

    os.makedirs(
        debug_dir,
        exist_ok=True
    )

    RESTART_EVERY = 10

    PER_NUMBER_HARD_TIMEOUT = 90

    try:

        with sync_playwright() as playwright:

            browser, context, page = start_browser(
                playwright
            )

            print(
                f"✅ Started on: {target_url}"
            )

            # ------------------------------------------------
            # READ NUMBERS
            # ------------------------------------------------

            with open(
                numbers_file,
                "r",
                encoding="utf-8"
            ) as file:

                numbers = [
                    line.strip()
                    for line in file
                    if line.strip()
                ]

            print(
                f"📋 Loaded {len(numbers)} numbers"
            )

            # ------------------------------------------------
            # PROCESS NUMBERS
            # ------------------------------------------------

            for i, num in enumerate(
                numbers,
                1
            ):

                if (
                    stop_event is not None
                    and stop_event.is_set()
                ):

                    print(
                        f"🛑 Stop requested. "
                        f"Halting after "
                        f"{i - 1}/{len(numbers)} numbers."
                    )

                    break

                print(
                    f"\n[{i}/{len(numbers)}] "
                    f"Processing: {num}"
                )

                # --------------------------------------------
                # RESTART BROWSER
                # --------------------------------------------

                if (
                    i > 1
                    and (i - 1) % RESTART_EVERY == 0
                ):

                    print(
                        f"   🔄 Restarting browser "
                        f"after {i - 1} numbers..."
                    )

                    try:
                        browser.close()
                    except Exception:
                        pass

                    time.sleep(2)

                    try:

                        browser, context, page = (
                            start_browser(playwright)
                        )

                        print(
                            "   ✅ Browser restarted"
                        )

                    except Exception as error:

                        print(
                            f"   ❌ Browser restart "
                            f"failed: {error}"
                        )

                        continue

                # --------------------------------------------
                # PROCESS
                # --------------------------------------------

                executor = (
                    concurrent.futures.ThreadPoolExecutor(
                        max_workers=1
                    )
                )

                future = executor.submit(
                    process_one_number,
                    page,
                    target_url,
                    num,
                    debug_dir
                )

                try:

                    future.result(
                        timeout=PER_NUMBER_HARD_TIMEOUT
                    )

                    print(
                        f"   ✅ {num} "
                        f"completed successfully."
                    )

                    executor.shutdown(
                        wait=False
                    )

                except concurrent.futures.TimeoutError:

                    print(
                        f"   ⏱️ {num} timed out "
                        f"after "
                        f"{PER_NUMBER_HARD_TIMEOUT}s."
                    )

                    executor.shutdown(
                        wait=False
                    )

                    try:
                        browser.close()
                    except Exception:
                        pass

                    time.sleep(2)

                    try:

                        browser, context, page = (
                            start_browser(playwright)
                        )

                        print(
                            "   ✅ New browser started"
                        )

                    except Exception as error:

                        print(
                            f"   ❌ Could not start "
                            f"new browser: {error}"
                        )

                except Exception as error:

                    print(
                        f"   ❌ Error for {num}: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )

                    executor.shutdown(
                        wait=False
                    )

            print(
                "\n✅ All done!"
            )

            return (
                "Automation completed successfully!"
            )

    except Exception as error:

        print(
            f"❌ Critical Error: "
            f"{type(error).__name__}: {error}"
        )

        return f"Critical Error: {error}"

    finally:

        if browser:

            try:
                browser.close()
            except Exception:
                pass