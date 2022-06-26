import os
import shutil
import time
import traceback
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import urlparse

import undetected_chromedriver as uc
from browser_cookie3 import chrome as chrome_cookies
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from win32api import HIWORD, GetFileVersionInfo

from . import timedelta_loc
from .style import Style


def _get_chrome_main_version():
    filename = uc.find_chrome_executable()
    info = GetFileVersionInfo(filename, "\\")
    return HIWORD(info["FileVersionMS"])


def _get_xpath_loc(xpath):
    if type(xpath) in (tuple, list):
        xpath = " | ".join(xpath)
    return By.XPATH, xpath


def _find(find_func, xpath):
    locator = _get_xpath_loc(xpath)
    return find_func(*locator)


class Chrome(uc.Chrome):
    # faster load without images
    prefs = {"profile.managed_default_content_settings.images": 2}
    profile_folder = "profile"
    error_folder = "error"

    def __init__(self, page_load_timeout=10, wait_elt_timeout=5, log=None):
        options = uc.ChromeOptions()
        options.headless = True
        options.add_experimental_option("prefs", Chrome.prefs)
        # pylint: disable=unnecessary-lambda
        self.error = None
        self.log = log or (lambda *args: print(*args))

        # profile to keep the caches & cookies
        os.makedirs(Chrome.profile_folder, exist_ok=True)

        super().__init__(
            options=options,
            version_main=_get_chrome_main_version(),
            user_data_dir=os.path.abspath(Chrome.profile_folder),
        )

        self.set_page_load_timeout(page_load_timeout)
        self._wait_elt_timeout = wait_elt_timeout
        self._driver_wait = WebDriverWait(self, wait_elt_timeout)

    def _are_local_cookies_valid(self, domain):
        for file in ("Default\\Cookies", "Default\\Network\\Cookies"):
            file = os.path.join(Chrome.profile_folder, file)
            if os.path.exists(file):
                in_2mn = time.time() + 120
                if cookies := chrome_cookies(domain_name=domain, cookie_file=file):
                    return all(not cookie.is_expired(now=in_2mn) for cookie in cookies)
        return False

    def _preload_cookies_from_chrome(self, domain):
        cookies = chrome_cookies(domain_name=domain)
        cookie_keys = "domain", "name", "value", "path", "expires"

        self.execute_cdp_cmd("Network.enable", {})
        for cookie in cookies:
            cookie = {key: getattr(cookie, key) for key in cookie_keys}
            self.execute_cdp_cmd("Network.setCookie", cookie)
        self.execute_cdp_cmd("Network.disable", {})

        if expires := (cookie.expires for cookie in cookies):
            expire = datetime.now() - datetime.fromtimestamp(min(expires))
            self.log("expirent dans ", Style(timedelta_loc(expire)).bold)

    def load_cookies(self, url):
        domain = urlparse(url).netloc
        # do local profile cookies are valid ?
        if not self._are_local_cookies_valid(domain):
            # preload cookies from the regular Chrome profile
            self.log("Charge les cookies de ", Style(domain).bold)
            self._preload_cookies_from_chrome(domain)

    def wait_until(self, until, timeout=None):
        if timeout and timeout != self._wait_elt_timeout:
            return WebDriverWait(self, timeout).until(until)
        return self._driver_wait.until(until)

    def wait_for(self, xpath, expected_condition, timeout=None):
        locator = _get_xpath_loc(xpath)
        return self.wait_until(expected_condition(locator), timeout)

    def wait_for_clickable(self, xpath, timeout=None):
        return self.wait_for(xpath, EC.element_to_be_clickable, timeout)

    def xpath(self, xpath):
        return _find(self.find_element, xpath)

    def xpaths(self, xpath):
        return _find(self.find_elements, xpath)

    # fix UC contextual manager
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.error = SimpleNamespace(
                name=exc_type.__name__,
                file=os.path.split(exc_tb.tb_frame.f_code.co_filename)[1],
                line=exc_tb.tb_lineno,
            )
            self._save_error(traceback.format_exc(), datetime.now())
        self.quit()
        return True

    def _save_error(self, error_log, error_date):
        # remove all previous errors folders
        if os.path.exists(Chrome.error_folder):
            for filename in os.listdir(Chrome.error_folder):
                file_path = os.path.join(Chrome.error_folder, filename)
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)

        # write the errors files
        folder = os.path.join(Chrome.error_folder, f"{error_date:%Y_%m_%d_at_%H_%M_%S}")
        os.makedirs(folder, exist_ok=True)
        filename = os.path.join(folder, Chrome.error_folder)
        try:
            with open(f"{filename}.html", "w", encoding="utf8") as f:
                f.write(self.page_source)

            with open(f"{filename}.txt", "w", encoding="utf8") as f:
                f.write(error_log)

        # pylint: disable=broad-except
        except Exception as err:
            print(f"can't save error page : {err}")
