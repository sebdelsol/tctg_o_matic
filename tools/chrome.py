import os
import shutil
import traceback
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import urlparse

import browser_cookie3
import undetected_chromedriver as uc
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
        options.add_experimental_option("prefs", self.prefs)
        # pylint: disable=unnecessary-lambda
        self.error = None
        self.log = log or (lambda *args: print(*args))

        # profile to keep the caches & cookies
        os.makedirs(self.profile_folder, exist_ok=True)

        super().__init__(
            options=options,
            version_main=_get_chrome_main_version(),
            user_data_dir=os.path.abspath(self.profile_folder),
        )

        self.set_page_load_timeout(page_load_timeout)
        self._wait_elt_timeout = wait_elt_timeout
        self._driver_wait = WebDriverWait(self, wait_elt_timeout)

    def find_local_cookies(self, domain):
        for cookies in ("Default\\Cookies", "Default\\Network\\Cookies"):
            cookies = os.path.join(self.profile_folder, cookies)
            if os.path.exists(cookies):
                return browser_cookie3.chrome(domain_name=domain, cookie_file=cookies)
        return None

    def load_cookies(self, url):
        domain = urlparse(url).netloc
        # do those cookies already exist in the local profile ?
        if not self.find_local_cookies(domain):
            # preload cookies from the regular Chrome profile
            self.log("Charge les cookies de ", Style(domain).bold)
            self.execute_cdp_cmd("Network.enable", {})
            cookie_keys = "domain", "name", "value", "path", "expires"
            expires = []
            for cookie in browser_cookie3.chrome(domain_name=domain):
                expires.append(datetime.fromtimestamp(cookie.expires))
                cookie = {key: getattr(cookie, key) for key in cookie_keys}
                self.execute_cdp_cmd("Network.setCookie", cookie)
            self.execute_cdp_cmd("Network.disable", {})

            if expires:
                expire = timedelta_loc(datetime.now() - min(expires))
                self.log("expirent dans ", Style(expire).bold)

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
        if os.path.exists(self.error_folder):
            for filename in os.listdir(self.error_folder):
                file_path = os.path.join(self.error_folder, filename)
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)

        # write the errors files
        folder = os.path.join(self.error_folder, f"{error_date:%Y_%m_%d_at_%H_%M_%S}")
        os.makedirs(folder, exist_ok=True)
        filename = os.path.join(folder, self.error_folder)
        try:
            with open(f"{filename}.html", "w", encoding="utf8") as f:
                f.write(self.page_source)

            with open(f"{filename}.txt", "w", encoding="utf8") as f:
                f.write(error_log)

        # pylint: disable=broad-except
        except Exception as err:
            print(f"can't save error page : {err}")
