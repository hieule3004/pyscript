import json
import os
import sys
from datetime import datetime
from functools import partial, reduce, wraps
from typing import Callable

from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import Chrome, ChromeOptions, ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup


# === Utils === #

def star(f):
    @wraps(f)
    def f_inner(args):
        return f(*args)

    return f_inner


def where(path: str, extension: str = None):
    def __path_match(root, _dirs, files):
        _filenames = files
        if extension:
            _filenames = filter(lambda s: s.endswith(extension), _filenames)
        _filenames = map(partial(os.path.join, os.getcwd(), root), _filenames)
        return list(_filenames)

    filenames = map(star(__path_match), os.walk(path))
    filenames = reduce(list.__add__, filenames)
    return filenames


# ============= #


class Driver(Chrome):
    def __init__(self,
                 executable_path: str = None,
                 binary_path: str = None,
                 download_path: str = None,
                 log_request=False,
                 headless=False,
                 ):
        logfile_path = None
        if log_request:
            now = datetime.now().strftime("%Y%m%d%H%M%S")
            logfile_path = os.path.join(os.getcwd(), 'out', 'logs', f'request.{now}.log')

        # update environment
        if not executable_path:
            executable_path = os.path.abspath(ChromeDriverManager().install())
        os.environ['webdriver.chrome.driver'] = executable_path

        options = ChromeOptions()
        # browser binary
        if binary_path:
            pass
        elif sys.platform == 'darwin':
            binary_path = where('/Applications', 'Google Chrome')[0]
        elif sys.platform == 'win32':
            binary_path = where(r'C:\Program Files\Google', 'chrome.exe')[0]
        else:
            raise Exception(f'unsupported platform: ${sys.platform}')
        options.binary_location = binary_path
        # general options
        options.add_argument('--start-maximized')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-extensions')
        # headless
        if headless:
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-setuid-sandbox')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-webgl')
        # download options
        if not download_path:
            download_path = os.path.join(os.getcwd(), 'out', 'download')
        options.add_experimental_option('prefs', {
            'download': {
                'default_directory': download_path,
                'prompt_for_download': False
            },
            'profile': {
                'default_content_setting_values': {
                    'automatic_downloads': 1,
                    'notifications': 2,
                    'popup': 2
                }
            }
        })
        # log outgoing requests
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        # accept all certs
        options.set_capability('acceptInsecureCerts', True)

        super().__init__(service=ChromeService(executable_path=executable_path), options=options)

        self.__logfile_path = logfile_path

        print(f'executable_path={executable_path}')
        print(f'binary_path={binary_path}')
        print(f'logfile_path={logfile_path}')
        print(f'download_path={download_path}')

    def requests_sent(self, *_args):
        logs = self.get_log('performance')
        if self.__logfile_path:
            with open(f'{self.__logfile_path}', mode='a', errors=None) as logfile:
                for log in logs:
                    logfile.write(json.dumps(json.loads(log['message']), indent=2))
        is_loaded = len(logs) == 0
        # self.implicitly_wait(2 if is_loaded else 0)
        return is_loaded

    def wait(self, wait_func: Callable = requests_sent):
        WebDriverWait(driver=self, timeout=60).until(wait_func)


def main():
    driver = Driver(log_request=False, )
    driver.get('https://www.saucedemo.com')
    driver.wait()

    # username = (By.ID, 'user-name')
    # driver.wait(EC.element_to_be_clickable(username))
    # driver.find_element(*username).send_keys('standard_user')
    #
    # password = (By.ID, 'password')
    # driver.wait(EC.element_to_be_clickable(password))
    # driver.find_element(*password).send_keys('secret_sauce')
    #
    # submit = (By.ID, 'login-button')
    # driver.wait(EC.element_to_be_clickable(submit))
    # driver.find_element(*submit).click()
    #

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    with open(os.path.join('out', '_.html'), 'wb') as file:
        file.write(soup.prettify('utf-8'))
    while True:
        __import__('time').sleep(60)
    # driver.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
