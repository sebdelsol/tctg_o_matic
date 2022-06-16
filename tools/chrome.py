import os
import shutil
from urllib.parse import urlparse

import browser_cookie3
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from win32api import HIWORD, GetFileVersionInfo


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


class EnhancedChrome(uc.Chrome):
    # faster load without images
    prefs = {"profile.managed_default_content_settings.images": 2}
    profile = "profile"
    error = "error"

    def __init__(self, page_load_timeout=10, wait_elt_timeout=5):
        options = uc.ChromeOptions()
        options.headless = True
        options.add_experimental_option("prefs", self.prefs)

        # profile to keep the caches & cookies
        os.makedirs(self.profile, exist_ok=True)

        super().__init__(
            options=options,
            version_main=_get_chrome_main_version(),
            user_data_dir=os.path.abspath(self.profile),
        )

        self.set_page_load_timeout(page_load_timeout)
        self._wait_elt_timeout = wait_elt_timeout
        self._driver_wait = WebDriverWait(self, wait_elt_timeout)

    def find_local_cookies(self, domain):
        for cookie_file in ("Default\\Cookies", "Default\\Network\\Cookies"):
            cookie_file = os.path.join(self.profile, cookie_file)
            if os.path.exists(cookie_file):
                return browser_cookie3.chrome(
                    domain_name=domain, cookie_file=cookie_file
                )
        return None

    def load_cookies(self, url):
        domain = urlparse(url).netloc
        # do those cookies already exist in the local profile ?
        if not self.find_local_cookies(domain):
            print(" • Load cookies")
            # get those from the regular Chrome profile
            self.get(url)
            for cookie in browser_cookie3.chrome(domain_name=domain):
                self.add_cookie(
                    {
                        "name": cookie.name,
                        "value": cookie.value,
                        "path": cookie.path,
                        "expiry": cookie.expires,
                    }
                )

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

    def save_error(self, error_log, error_date):
        # remove all previous errors folders
        if os.path.exists(self.error):
            for filename in os.listdir(self.error):
                file_path = os.path.join(self.error, filename)
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)

        # write the errors files
        folder = os.path.join(self.error, f"{error_date:%Y_%m_%d_at_%H_%M_%S}")
        os.makedirs(folder, exist_ok=True)
        filename = os.path.join(folder, self.error)
        try:
            with open(f"{filename}.html", "w", encoding="utf8") as f:
                f.write(self.page_source)

            with open(f"{filename}.txt", "w", encoding="utf8") as f:
                f.write(error_log)

        # pylint: disable=broad-except
        except Exception:
            print("can't save error page")
