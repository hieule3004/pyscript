import json
import math
import os
import sys
from datetime import datetime
from functools import partial, reduce, wraps

import requests
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import Chrome, ChromeOptions, ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
from PIL import Image as PillowImage


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
                 wait_timeout=60,
                 ):
        logfile_path = None
        if log_request:
            now = datetime.now().strftime("%Y%m%d%H%M%S")
            logfile_path = os.path.join(os.getcwd(), 'out', 'logs', f'request.{now}.log')
            os.makedirs(logfile_path, exist_ok=True)

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
        os.makedirs(download_path, exist_ok=True)

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
        self.wait = WebDriverWait(driver=self, timeout=wait_timeout)

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
        self.get_network_conditions()
        return is_loaded


def main():
    base_url = 'https://www.saucedemo.com'
    html_path = os.path.join('out', 'out.html')
    if os.path.exists(html_path):
        with open(html_path, 'r') as html_file:
            html = html_file.read()
    else:
        driver = Driver(log_request=False, headless=True)

        driver.get(base_url)

        username = (By.ID, 'user-name')
        driver.wait.until(EC.element_to_be_clickable(username))
        driver.find_element(*username).send_keys('standard_user')

        password = (By.ID, 'password')
        driver.wait.until(EC.element_to_be_clickable(password))
        driver.find_element(*password).send_keys('secret_sauce')

        submit = (By.ID, 'login-button')
        driver.wait.until(EC.element_to_be_clickable(submit))
        driver.find_element(*submit).click()

        html = driver.page_source
        driver.quit()

    # html parse tree
    soup = BeautifulSoup(html, 'html.parser')
    if not os.path.exists(html_path):
        with open(html_path, 'wb') as html_file:
            html_file.write(soup.prettify('utf-8'))

    # tabular data
    rows = [[
        e.find('img', {'class': 'inventory_item_img'}).attrs['src'],
        e.find('div', {'class': 'inventory_item_name'}).text,
        e.find('div', {'class': 'inventory_item_desc'}).text,
        e.find('div', {'class': 'inventory_item_price'}).text,
    ] for i, e in enumerate(soup.find_all('div', {'class': 'inventory_item'}))]

    header = ['image', 'name', 'description', 'price']
    df = pd.DataFrame(rows, columns=header)

    with pd.ExcelWriter(os.path.join('out', 'out.xlsx'), engine='xlsxwriter') as writer:
        writer.book.add_format({'text_wrap': 1, 'text_v_align': 'top'})
        df.to_excel(writer, sheet_name='Sheet')
        ws = writer.sheets['Sheet']

        cw, ch = 128, 192
        img_col_idx = df.columns.get_loc('image') + 1
        for i, path in enumerate(df['image']):
            img_path = os.path.join('out', 'download', os.path.basename(path))
            if not os.path.exists(img_path):
                # download image
                with open(img_path, 'wb') as img_file:
                    img_file.write(requests.get(f'{base_url}{path}').raw)
            # replace url path with image
            iw, ih = PillowImage.open(img_path).size
            letter = chr(ord("A") + img_col_idx)
            ws.insert_image(f'{letter}{i + 2}', img_path, {'x_scale': cw / iw, 'y_scale': ch / ih})
            ws.write_string(i + 1, img_col_idx, '')

        # resize cells
        ws.autofit()
        ws.set_column(img_col_idx, img_col_idx, 17.6)
        for idx in range(len(df.index)):
            ws.set_row(idx + 1, 0.75 * ch)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
