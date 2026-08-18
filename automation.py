from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
    NoSuchElementException,
)
from webdriver_manager.chrome import ChromeDriverManager

import time
import os
import concurrent.futures
import threading


# ============================================================
# BROWSER CLEANUP
# ============================================================

def safe_quit(driver):
    def close():
        try:
            driver.quit()
        except Exception:
            pass

    threading.Thread(target=close, daemon=True).start()


# ============================================================
# CLICK HELPER
# ============================================================

def robust_click(driver, element):
    try:
        element.click()
        return True
    except StaleElementReferenceException:
        raise
    except Exception:
        pass

    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block:'center'});",
            element
        )
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", element)
        return True
    except Exception:
        pass

    try:
        ActionChains(driver).move_to_element(element).pause(0.2).click().perform()
        return True
    except Exception:
        return False


# ============================================================
# FIND ELEMENT IN PAGE / IFRAMES
# ============================================================

def find_in_page_or_frames(driver, xpaths, timeout=15):
    end_time = time.time() + timeout

    while time.time() < end_time:

        driver.switch_to.default_content()

        for xpath in xpaths:
            try:
                elements = driver.find_elements(By.XPATH, xpath)

                for element in elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            return element, None
                    except StaleElementReferenceException:
                        continue
            except Exception:
                continue

        try:
            frames = driver.find_elements(By.TAG_NAME, "iframe")

            for frame in frames:
                try:
                    driver.switch_to.default_content()
                    driver.switch_to.frame(frame)

                    for xpath in xpaths:
                        try:
                            elements = driver.find_elements(By.XPATH, xpath)

                            for element in elements:
                                try:
                                    if element.is_displayed() and element.is_enabled():
                                        return element, frame
                                except StaleElementReferenceException:
                                    continue
                        except Exception:
                            continue

                except Exception:
                    continue

        except Exception:
            pass

        driver.switch_to.default_content()
        time.sleep(0.5)

    driver.switch_to.default_content()
    return None, None


# ============================================================
# DEBUG
# ============================================================

def save_debug(driver, debug_dir, name, num):
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
        driver.switch_to.default_content()
        driver.save_screenshot(screenshot)

        with open(html, "w", encoding="utf-8") as file:
            file.write(driver.page_source)

        print(f"   📸 Screenshot: {screenshot}")
        print(f"   📄 HTML: {html}")

    except Exception as error:
        print(f"   ⚠️ Could not save debug files: {error}")


# ============================================================
# START DRIVER
# ============================================================

def start_driver():
    options = Options()

    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--mute-audio")

    service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(
        service=service,
        options=options
    )

    try:
        driver.command_executor.set_timeout(30)
    except Exception:
        pass

    driver.set_page_load_timeout(35)
    driver.set_script_timeout(30)

    return driver


# ============================================================
# CLOUDFLARE DETECTION
# ============================================================

def is_cloudflare_page(driver):
    try:
        title = (driver.title or "").lower()
        source = driver.page_source.lower()

        indicators = [
            "attention required! | cloudflare",
            "attention required",
            "cloudflare",
            "cf-chl-",
            "challenge-platform",
            "verify you are human",
        ]

        return any(indicator in title or indicator in source
                   for indicator in indicators)

    except Exception:
        return False


# ============================================================
# LOGIN SELECTORS
# ============================================================

MOBILE_XPATHS = [
    "//input[@type='tel']",
    "//input[contains(translate(@name,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'mobile')]",
    "//input[contains(translate(@name,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'phone')]",
    "//input[contains(translate(@name,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'number')]",
    "//input[contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'mobile')]",
    "//input[contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'phone')]",
    "//input[contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'number')]",
    "//input[contains(translate(@placeholder,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'mobile')]",
    "//input[contains(translate(@placeholder,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'phone')]",
    "//input[contains(translate(@placeholder,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'number')]",
    "//input[@autocomplete='tel']",
]

PASSWORD_XPATHS = [
    "//input[@type='password']",
    "//input[contains(translate(@name,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'password')]",
    "//input[contains(translate(@id,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'password')]",
    "//input[contains(translate(@placeholder,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'password')]",
]

LOGIN_XPATHS = [
    "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'login')]",
    "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'log in')]",
    "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]",
    "//button[@type='submit']",
    "//input[@type='submit']",
]

DAILY_COIN_XPATHS = [
    "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'daily coin')]",
    "//*[@role='button'][contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'daily coin')]",
    "//a[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'daily coin')]",
    "//*[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'daily coins')]",
    "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'dailycoin')]",
]

SIGN_IN_XPATHS = [
    "//button[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]",
    "//*[@role='button'][contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]",
    "//a[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]",
    "//*[contains(translate(normalize-space(.),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]",
]


# ============================================================
# PROCESS ONE NUMBER
# ============================================================

def process_one_number(driver, wait, target_url, num, debug_dir):

    print(f"   🌐 Opening: {target_url}")

    driver.get(target_url)
    time.sleep(5)

    print(f"   🌐 Current URL: {driver.current_url}")
    print(f"   📄 Page title: {driver.title}")

    # --------------------------------------------------------
    # IMPORTANT FIX:
    # Stop immediately if Railway receives Cloudflare instead
    # of the actual login page.
    # --------------------------------------------------------

    if is_cloudflare_page(driver):
        save_debug(
            driver,
            debug_dir,
            "cloudflare_blocked",
            num
        )

        raise TimeoutException(
            "Cloudflare page detected. "
            "The actual login page was not loaded."
        )

    # --------------------------------------------------------
    # MOBILE
    # --------------------------------------------------------

    print("   🔎 Looking for mobile/number input...")

    mobile, _ = find_in_page_or_frames(
        driver,
        MOBILE_XPATHS,
        timeout=15
    )

    if mobile is None:
        save_debug(
            driver,
            debug_dir,
            "mobile_input_not_found",
            num
        )

        raise TimeoutException(
            "Could not find mobile/number input."
        )

    mobile.clear()
    mobile.send_keys(num)

    print(f"   📱 Number entered: {num}")

    # --------------------------------------------------------
    # PASSWORD
    # --------------------------------------------------------

    print("   🔎 Looking for password input...")

    password, _ = find_in_page_or_frames(
        driver,
        PASSWORD_XPATHS,
        timeout=15
    )

    if password is None:
        save_debug(
            driver,
            debug_dir,
            "password_input_not_found",
            num
        )

        raise TimeoutException(
            "Could not find password input."
        )

    password.clear()
    password.send_keys(num)

    print("   🔑 Password entered")

    # --------------------------------------------------------
    # LOGIN
    # --------------------------------------------------------

    print("   🔎 Looking for Login button...")

    login_btn, _ = find_in_page_or_frames(
        driver,
        LOGIN_XPATHS,
        timeout=15
    )

    if login_btn is None:
        save_debug(
            driver,
            debug_dir,
            "login_button_not_found",
            num
        )

        raise TimeoutException(
            "Could not find Login button."
        )

    if not robust_click(driver, login_btn):
        raise ElementClickInterceptedException(
            "Could not click Login button."
        )

    driver.switch_to.default_content()

    print("   ✅ Login clicked")

    time.sleep(7)

    # --------------------------------------------------------
    # DAILY COINS
    # --------------------------------------------------------

    print("   🔎 Looking for 'Daily coins' button...")

    daily_btn, _ = find_in_page_or_frames(
        driver,
        DAILY_COIN_XPATHS,
        timeout=15
    )

    if daily_btn is None:
        save_debug(
            driver,
            debug_dir,
            "daily_coin_not_found",
            num
        )

        raise TimeoutException(
            "Could not find Daily Coins button."
        )

    if not robust_click(driver, daily_btn):
        raise ElementClickInterceptedException(
            "Could not click Daily Coins button."
        )

    driver.switch_to.default_content()

    print("   ✅ Clicked 'Daily coins'!")

    time.sleep(4)

    # --------------------------------------------------------
    # SIGN IN
    # --------------------------------------------------------

    print("   🔎 Looking for 'Sign In' button...")

    sign_btn, _ = find_in_page_or_frames(
        driver,
        SIGN_IN_XPATHS,
        timeout=15
    )

    if sign_btn is None:
        save_debug(
            driver,
            debug_dir,
            "sign_in_not_found",
            num
        )

        raise TimeoutException(
            "Could not find Sign In button."
        )

    if not robust_click(driver, sign_btn):
        raise ElementClickInterceptedException(
            "Could not click Sign In button."
        )

    driver.switch_to.default_content()

    print("   ✅ Clicked Sign In!")


# ============================================================
# MAIN AUTOMATION
# ============================================================

def run_automation(target_url, numbers_file, stop_event=None):

    driver = None
    debug_dir = "debug_output"

    os.makedirs(debug_dir, exist_ok=True)

    # Restart browser every 10 numbers.
    RESTART_EVERY = 10

    # Maximum time allowed for one number.
    PER_NUMBER_HARD_TIMEOUT = 90

    try:

        driver = start_driver()
        wait = WebDriverWait(driver, 20)

        print(f"✅ Started on: {target_url}")

        # ----------------------------------------------------
        # READ NUMBERS
        # ----------------------------------------------------

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

        print(f"📋 Loaded {len(numbers)} numbers")

        # ----------------------------------------------------
        # PROCESS NUMBERS
        # ----------------------------------------------------

        for i, num in enumerate(numbers, 1):

            if stop_event is not None and stop_event.is_set():

                print(
                    f"🛑 Stop requested. "
                    f"Halting after {i - 1}/{len(numbers)} numbers."
                )

                break

            print(
                f"\n[{i}/{len(numbers)}] Processing: {num}"
            )

            # ------------------------------------------------
            # RESTART BROWSER PERIODICALLY
            # ------------------------------------------------

            if i > 1 and (i - 1) % RESTART_EVERY == 0:

                print(
                    f"   🔄 Restarting browser after "
                    f"{i - 1} numbers..."
                )

                safe_quit(driver)
                time.sleep(2)

                try:
                    driver = start_driver()
                    wait = WebDriverWait(driver, 20)

                    print("   ✅ Browser restarted")

                except Exception as error:

                    print(
                        f"   ❌ Browser restart failed: {error}"
                    )

                    continue

            # ------------------------------------------------
            # RUN NUMBER WITH HARD TIMEOUT
            # ------------------------------------------------

            executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=1
            )

            future = executor.submit(
                process_one_number,
                driver,
                wait,
                target_url,
                num,
                debug_dir
            )

            try:

                future.result(
                    timeout=PER_NUMBER_HARD_TIMEOUT
                )

                print(
                    f"   ✅ {num} completed successfully."
                )

                executor.shutdown(wait=False)

            except concurrent.futures.TimeoutError:

                print(
                    f"   ⏱️ {num} timed out after "
                    f"{PER_NUMBER_HARD_TIMEOUT}s."
                )

                executor.shutdown(wait=False)
                safe_quit(driver)

                time.sleep(2)

                try:
                    driver = start_driver()
                    wait = WebDriverWait(driver, 20)

                    print("   ✅ New browser started")

                except Exception as error:

                    print(
                        f"   ❌ Could not start new browser: "
                        f"{error}"
                    )

            except Exception as error:

                print(
                    f"   ❌ Error for {num}: "
                    f"{type(error).__name__}: {error}"
                )

                executor.shutdown(wait=False)

                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass

        print("\n✅ All done!")

        return "Automation completed successfully!"

    except Exception as error:

        print(
            f"❌ Critical Error: "
            f"{type(error).__name__}: {error}"
        )

        return f"Critical Error: {error}"

    finally:

        if driver:
            safe_quit(driver)