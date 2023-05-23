import os
import sys
import django
import re
import json
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

from twill.commands import *
from twill import browser
from bs4 import BeautifulSoup

site = 'https://anspd.ru'
centers = ['UIII', 'UWWW', 'UEEE', 'ULLL', 'UNKL', 'UNNT', 'URRR', 'USSV', 'USTU', 'UUUU', 'UUYY', 'UHMM', 'UHPP', 'UHHH']
#base_dir = f'{os.path.abspath("./")}'
base_dir = Path(__file__).resolve().parent.parent
tmp_dir = f'{base_dir}/begining/backend/tmp/'
setting_dir = f'{base_dir}/begining/'
routes = ['AMHS']

def authentication():
    with open(f'{setting_dir}setting.json', 'r') as f:
        setting = json.load(f)
    LOGIN = setting['LOGIN']
    PASS = setting['PASS']
    browser.go(site)
    fv('1', 'login', LOGIN)
    fv('1', 'pass', PASS)
    submit()
    #info()
    file_index = f'{os.path.abspath("./")}/begining/backend/tmp/index.html'
    save_html(file_index)

    follow_link = site + parse_index(file_index)
    browser.go(follow_link)
    file_uhhh = f'{os.path.abspath("./")}/begining/backend/tmp/uhhh.html'
    save_html(file_uhhh)

def parse_index(file_test):
    with open(file_test, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
        href_actual = soup.find(name='a', text=re.compile('Просмотр действующих данных')).get('href')
        href_center = soup.find(name='a', attrs={'href': re.compile(href_actual)}, text=re.compile('UHHH')).get('href')
        href_center = re.sub(f'{href_actual}\?', '', href_center)
        href_amhs = soup.find(name='a', attrs={'href': re.compile(href_center)}, text=re.compile('AMHS')).get('href')

        return href_amhs

if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
    sys.path.append('C:/Users/admin/OneDrive/Документы/GitHubRepo/WebTest/begining')
    django.setup()
    
    authentication()
    #file_test = f'{os.path.abspath("./")}/begining/backend/tmp/index.html'
    #parse_index(file_test)