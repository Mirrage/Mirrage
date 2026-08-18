from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
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


# ================================================================
# SAFE BROWSER CLEANUP
# ================================================================

def safe_quit(driver):
    """Quit Chrome without allowing a frozen browser to block cleanup."""
    def _quit():
        try:
            driver.quit()
        except Exception:
            pass

    threading.Thread(target=_quit, daemon=True).start()


# ================================================================
# ROBUST CLICK
# ================================================================

def robust_click(driver, element):
    """
    Try a normal Selenium click, then JavaScript, then ActionChains.
    """
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


# ================================================================
# FIND ELEMENT IN PAGE OR IFRAMES
# ================================================================

def find_in_page_or_frames(driver, xpaths, timeout=20):
    """
    Search the main document and first-level iframes.

    Returns:
        (element, frame_context)

    frame_context is None when the element is in the main document.
    When an element is found inside an iframe, Selenium remains inside
    that iframe so the caller can interact with the returned element.
    """

    end_time = time.time() + timeout

    while time.time() < end_time:

        # --------------------------------------------------------
        # MAIN DOCUMENT
        # --------------------------------------------------------
        driver.switch_to.default_content()

        for xp in xpaths:
            try:
                elements = driver.find_elements(By.XPATH, xp)

                for element in elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            return element, None
                    except StaleElementReferenceException:
                        continue

            except Exception:
                continue

        # --------------------------------------------------------
        # IFRAMES
        # --------------------------------------------------------
        try:
            frames = driver.find_elements(By.TAG_NAME, "iframe")

            for frame in frames:
                try:
                    driver.switch_to.default_content()
                    driver.switch_to.frame(frame)

                    for xp in xpaths:
                        try:
                            elements = driver.find_elements(By.XPATH, xp)

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


# ================================================================
# CLOSE OPTIONAL POPUP
# ================================================================

def dismiss_close_popup(driver, timeout=5):
    """
    Close common X/Close popup buttons if one is present.
    This is optional and does not raise an error if nothing is found.
    """

    close_xpaths = [
        "//*[@aria-label='Close']",
        "//*[@aria-label='close']",
        "//*[@aria-label='Dismiss']",
        "//button[contains(@class,'close')]",
        "//*[contains(@class,'modal-close')]",
        "//*[contains(@class,'btn-close')]",
        "//*[contains(@class,'close-btn')]",
        "//*[contains(@class,'popup-close')]",
        "//button[normalize-space(text())='×']",
        "//button[normalize-space(text())='X']",
        "//span[normalize-space(text())='×']",
        "//*[@role='button'][normalize-space(text())='×']",
    ]

    close_btn, _ = find_in_page_or_frames(
        driver,
        close_xpaths,
        timeout=timeout
    )

    if close_btn is None:
        driver.switch_to.default_content()
        return False

    try:
        robust_click(driver, close_btn)
    except Exception:
        pass

    driver.switch_to.default_content()
    time.sleep(1)
    print("   ✅ Optional popup closed")
    return True


# ================================================================
# DEBUG INFORMATION
# ================================================================

def save_debug(driver, debug_dir, prefix, num):
    """Save screenshot and HTML so a failed page can be inspected."""

    os.makedirs(debug_dir, exist_ok=True)

    safe_num = str(num).replace("/", "_").replace("\\", "_")

    screenshot_path = os.path.join(
        debug_dir,
        f"{prefix}_{safe_num}.png"
    )

    html_path = os.path.join(
        debug_dir,
        f"{prefix}_{safe_num}.html"
    )

    try:
        driver.switch_to.default_content()
        driver.save_screenshot(screenshot_path)

        with open(html_path, "w", encoding="utf-8") as file:
            file.write(driver.page_source)

        print(f"   📸 Screenshot saved: {screenshot_path}")
        print(f"   📄 HTML saved: {html_path}")

    except Exception as error:
        print(f"   ⚠️ Could not save debug files: {error}")

    return screenshot_path, html_path


# ================================================================
# START CHROME
# ================================================================

def start_driver():
    """Create a fresh headless Chrome driver."""

    options = Options()

    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-setuid-sandbox")

    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-default-apps")
    options.add_argument("--mute-audio")

    options.add_argument("--disable-features=TranslateUI,site-per-process")
    options.add_argument("--renderer-process-limit=1")
    options.add_argument("--disk-cache-size=0")
    options.add_argument("--window-size=1280,900")

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option(
        "excludeSwitches",
        ["enable-automation"]
    )
    options.add_experimental_option(
        "useAutomationExtension",
        False
    )

    # Do not delete webdriver-manager's cache on every restart.
    # This is more reliable on Railway.
    service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(
        service=service,
        options=options
    )

    try:
        driver.command_executor.set_timeout(30)
    except Exception:
        pass

    try:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', "
            "{get: () => undefined})"
        )
    except Exception:
        pass

    driver.set_page_load_timeout(35)
    driver.set_script_timeout(30)

    return driver


# ================================================================
# INPUT SELECTORS
# ================================================================

MOBILE_XPATHS = [
    # Phone/mobile input types
    "//input[@type='tel']",

    # Names
    "//input[contains(translate(@name,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'mobile')]",

    "//input[contains(translate(@name,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'phone')]",

    "//input[contains(translate(@name,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'number')]",

    # IDs
    "//input[contains(translate(@id,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'mobile')]",

    "//input[contains(translate(@id,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'phone')]",

    "//input[contains(translate(@id,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'number')]",

    # Placeholders
    "//input[contains(translate(@placeholder,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'mobile')]",

    "//input[contains(translate(@placeholder,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'phone')]",

    "//input[contains(translate(@placeholder,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'number')]",

    "//input[contains(translate(@placeholder,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'telephone')]",

    # Autocomplete
    "//input[@autocomplete='tel']",
    "//input[@autocomplete='tel-national']",
]

PASSWORD_XPATHS = [
    "//input[@type='password']",

    "//input[contains(translate(@name,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'password')]",

    "//input[contains(translate(@id,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'password')]",

    "//input[contains(translate(@placeholder,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'password')]",

    "//input[contains(translate(@autocomplete,"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'password')]",
]

LOGIN_BUTTON_XPATHS = [
    "//button[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'login')]",

    "//button[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'log in')]",

    "//button[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]",

    "//input[@type='submit']",
    "//button[@type='submit']",

    "//*[@role='button'][contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'login')]",

    "//*[@role='button'][contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]",

    # Last-resort button fallback
    "//button",
]

DAILY_COIN_XPATHS = [
    "//button[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'daily coin')]",

    "//*[@role='button'][contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'daily coin')]",

    "//a[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'daily coin')]",

    "//*[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'daily coins')]",

    "//button[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'dailycoin')]",

    "//*[@role='button'][contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'dailycoin')]",

    "//*[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'dailycoin')]",
]

SIGN_IN_XPATHS = [
    "//button[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]",

    "//*[@role='button'][contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]",

    "//a[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]",

    "//*[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'sign in')]",

    "//button[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'signin')]",

    "//*[contains(translate(normalize-space(.),"
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'signin')]",
]


# ================================================================
# FIND FALLBACK INPUT
# ================================================================

def find_second_visible_input(driver, timeout=8):
    """
    Fallback for pages where the input has no useful type/name/id/placeholder.
    Returns the second visible editable input.
    """

    end_time = time.time() + timeout

    while time.time() < end_time:

        driver.switch_to.default_content()

        try:
            inputs = driver.find_elements(By.TAG_NAME, "input")

            visible_inputs = []

            for element in inputs:
                try:
                    if not element.is_displayed() or not element.is_enabled():
                        continue

                    input_type = (
                        element.get_attribute("type") or ""
                    ).lower()

                    if input_type in [
                        "hidden",
                        "submit",
                        "button",
                        "checkbox",
                        "radio",
                    ]:
                        continue

                    visible_inputs.append(element)

                except StaleElementReferenceException:
                    continue

            if len(visible_inputs) >= 2:
                return visible_inputs[1], None

        except Exception:
            pass

        time.sleep(0.5)

    return None, None


# ================================================================
# PROCESS ONE NUMBER
# ================================================================

def process_one_number(driver, wait, target_url, num, debug_dir):
    """
    Complete automation flow for one number:

    1. Open target URL
    2. Enter number in mobile field
    3. Enter number in password field
    4. Click Login
    5. Close optional popup
    6. Click Daily Coins
    7. Click Sign In in the resulting popup
    """

    # ------------------------------------------------------------
    # OPEN TARGET PAGE
    # ------------------------------------------------------------

    print(f"   🌐 Opening: {target_url}")

    driver.get(target_url)

    # Railway can take longer to load than a local PC.
    time.sleep(7)

    print(f"   🌐 Current URL: {driver.current_url}")
    print(f"   📄 Page title: {driver.title}")

    # ------------------------------------------------------------
    # MOBILE / NUMBER FIELD
    # ------------------------------------------------------------

    print("   🔎 Looking for mobile/number input...")

    mobile, mobile_frame = find_in_page_or_frames(
        driver,
        MOBILE_XPATHS,
        timeout=25
    )

    # If no named/type-based mobile input was found, try the
    # first visible editable input.
    if mobile is None:

        print("   ⚠️ Specific mobile selectors did not match.")
        print("   🔎 Trying first visible editable input...")

        driver.switch_to.default_content()

        end_time = time.time() + 8

        while time.time() < end_time:
            try:
                inputs = driver.find_elements(By.TAG_NAME, "input")

                for element in inputs:
                    try:
                        if not element.is_displayed() or not element.is_enabled():
                            continue

                        input_type = (
                            element.get_attribute("type") or ""
                        ).lower()

                        if input_type not in [
                            "hidden",
                            "submit",
                            "button",
                            "checkbox",
                            "radio",
                            "password",
                        ]:
                            mobile = element
                            mobile_frame = None
                            break

                    except StaleElementReferenceException:
                        continue

                if mobile is not None:
                    break

            except Exception:
                pass

            time.sleep(0.5)

    if mobile is None:

        save_debug(
            driver,
            debug_dir,
            "mobile_input_not_found",
            num
        )

        raise TimeoutException(
            "Could not find the mobile/number input. "
            f"URL={driver.current_url} "
            f"Title={driver.title}"
        )

    print("   ✅ Mobile/number input found")

    # ------------------------------------------------------------
    # ENTER NUMBER
    # ------------------------------------------------------------

    try:
        mobile.click()
    except Exception:
        pass

    mobile.clear()
    mobile.send_keys(num)

    print(f"   📱 Number entered: {num}")

    # ------------------------------------------------------------
    # PASSWORD
    # ------------------------------------------------------------

    print("   🔎 Looking for password input...")

    password, password_frame = find_in_page_or_frames(
        driver,
        PASSWORD_XPATHS,
        timeout=20
    )

    if password is None:

        print("   ⚠️ Password selector did not match.")
        print("   🔎 Trying second visible input...")

        password, password_frame = find_second_visible_input(
            driver,
            timeout=8
        )

    if password is None:

        save_debug(
            driver,
            debug_dir,
            "password_input_not_found",
            num
        )

        raise TimeoutException(
            "Could not find password input. "
            f"URL={driver.current_url} "
            f"Title={driver.title}"
        )

    print("   ✅ Password input found")

    try:
        password.click()
    except Exception:
        pass

    password.clear()
    password.send_keys(num)

    print("   🔑 Password entered")

    # ------------------------------------------------------------
    # LOGIN BUTTON
    # ------------------------------------------------------------

    print("   🔎 Looking for Login button...")

    login_btn, login_frame = find_in_page_or_frames(
        driver,
        LOGIN_BUTTON_XPATHS,
        timeout=20
    )

    if login_btn is None:

        save_debug(
            driver,
            debug_dir,
            "login_button_not_found",
            num
        )

        raise TimeoutException(
            "Could not find Login button. "
            f"URL={driver.current_url} "
            f"Title={driver.title}"
        )

    print("   ✅ Login button found")

    if not robust_click(driver, login_btn):

        save_debug(
            driver,
            debug_dir,
            "login_click_failed",
            num
        )

        raise ElementClickInterceptedException(
            "Login button could not be clicked"
        )

    driver.switch_to.default_content()

    print("   ✅ Login clicked")

    # ------------------------------------------------------------
    # WAIT FOR LOGIN / REDIRECT
    # ------------------------------------------------------------

    time.sleep(8)

    print(f"   🌐 After login URL: {driver.current_url}")

    # ------------------------------------------------------------
    # OPTIONAL POPUP
    # ------------------------------------------------------------

    print("   🔎 Checking for optional popup...")

    dismiss_close_popup(
        driver,
        timeout=5
    )

    # ------------------------------------------------------------
    # DAILY COINS
    # ------------------------------------------------------------

    print("   🔎 Looking for 'Daily coins' button...")

    daily_btn, daily_frame = find_in_page_or_frames(
        driver,
        DAILY_COIN_XPATHS,
        timeout=25
    )

    if daily_btn is None:

        save_debug(
            driver,
            debug_dir,
            "daily_coin_not_found",
            num
        )

        raise TimeoutException(
            "Could not locate 'Daily coins' button. "
            f"URL={driver.current_url} "
            f"Title={driver.title}"
        )

    print("   ✅ Daily coins button found")

    if not robust_click(driver, daily_btn):

        save_debug(
            driver,
            debug_dir,
            "daily_coin_click_failed",
            num
        )

        raise ElementClickInterceptedException(
            "Daily coins button could not be clicked"
        )

    driver.switch_to.default_content()

    print("   ✅ Clicked 'Daily coins'!")

    # Give popup time to render.
    time.sleep(5)

    # ------------------------------------------------------------
    # SIGN IN
    # ------------------------------------------------------------

    print("   🔎 Looking for 'Sign In' button...")

    sign_btn, sign_frame = find_in_page_or_frames(
        driver,
        SIGN_IN_XPATHS,
        timeout=20
    )

    if sign_btn is None:

        save_debug(
            driver,
            debug_dir,
            "sign_in_not_found",
            num
        )

        raise TimeoutException(
            "Could not locate 'Sign In' button. "
            f"URL={driver.current_url} "
            f"Title={driver.title}"
        )

    print("   ✅ Sign In button found")

    if not robust_click(driver, sign_btn):

        save_debug(
            driver,
            debug_dir,
            "sign_in_click_failed",
            num
        )

        raise ElementClickInterceptedException(
            "Sign In button could not be clicked"
        )

    driver.switch_to.default_content()

    print("   ✅ Clicked Sign In!")


# ================================================================
# MAIN AUTOMATION LOOP
# ================================================================

def run_automation(target_url, numbers_file, stop_event=None):

    driver = None

    debug_dir = "debug_output"
    os.makedirs(debug_dir, exist_ok=True)

    # Restart Chrome periodically to control memory usage.
    RESTART_EVERY = 10

    # Increased from 60 seconds because Railway can be slower.
    PER_NUMBER_HARD_TIMEOUT = 90

    try:

        # --------------------------------------------------------
        # START BROWSER
        # --------------------------------------------------------

        driver = start_driver()
        wait = WebDriverWait(driver, 25)

        print(f"✅ Started on: {target_url}")

        # --------------------------------------------------------
        # READ NUMBERS
        # --------------------------------------------------------

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

        # --------------------------------------------------------
        # PROCESS EACH NUMBER
        # --------------------------------------------------------

        for i, num in enumerate(numbers, 1):

            if stop_event is not None and stop_event.is_set():

                print(
                    f"\n🛑 Stop requested. "
                    f"Halting after {i - 1}/{len(numbers)} numbers."
                )

                break

            print(
                f"\n[{i}/{len(numbers)}] Processing: {num}"
            )

            # ----------------------------------------------------
            # PERIODIC BROWSER RESTART
            # ----------------------------------------------------

            if i > 1 and (i - 1) % RESTART_EVERY == 0:

                print(
                    f"   🔄 Restarting browser after "
                    f"{i - 1} numbers..."
                )

                safe_quit(driver)

                time.sleep(2)

                try:

                    driver = start_driver()
                    wait = WebDriverWait(driver, 25)

                    print("   ✅ Browser restarted")

                except Exception as restart_error:

                    print(
                        f"   ❌ Failed to restart browser: "
                        f"{restart_error}"
                    )

                    continue

            # ----------------------------------------------------
            # RUN NUMBER IN WORKER THREAD
            # ----------------------------------------------------

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

            # ----------------------------------------------------
            # HARD TIMEOUT
            # ----------------------------------------------------

            except concurrent.futures.TimeoutError:

                print(
                    f"   ⏱️ {num} timed out after "
                    f"{PER_NUMBER_HARD_TIMEOUT}s."
                )

                print(
                    "   🔄 Browser may be frozen. "
                    "Starting a new browser..."
                )

                executor.shutdown(wait=False)

                safe_quit(driver)

                time.sleep(2)

                try:

                    driver = start_driver()
                    wait = WebDriverWait(driver, 25)

                    print(
                        "   ✅ New browser started"
                    )

                except Exception as restart_error:

                    print(
                        f"   ❌ Failed to start new browser: "
                        f"{restart_error}"
                    )

            # ----------------------------------------------------
            # NORMAL ERROR
            # ----------------------------------------------------

            except Exception as error:

                print(
                    f"   ❌ Error for {num}: "
                    f"{type(error).__name__}: {error}"
                )

                executor.shutdown(wait=False)

                try:
                    driver.switch_to.default_content()

                    save_debug(
                        driver,
                        debug_dir,
                        "error",
                        num
                    )

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