import os
import sys
import django
import re
import json
from pathlib import Path

from twill.commands import *
from twill import browser
from bs4 import BeautifulSoup

site = 'https://anspd.ru'
centers = ['UIII', 'UWWW', 'UEEE', 'ULLL', 'UNKL', 'UNNT', 'URRR', 'USSV', 'USTU', 'UUUU', 'UUYY', 'UHMM', 'UHPP', 'UHHH']
#base_dir = Path(__file__).resolve().parent.parent
base_dir = Path(__file__)
tmp_dir = Path(f'{Path(__file__).resolve().parent}/tmp/')
#setting_dir = f'{base_dir}/begining/'
setting_dir = Path(f'{Path(__file__).resolve().parent.parent}/begining/')

def parse_anspd():
    authentication()

def authentication():
    with open(setting_dir / 'setting.json', 'r') as f:
        setting = json.load(f)
    browser.go(site)
    fv('1', 'login', setting['LOGIN'])
    fv('1', 'pass', setting['PASS'])
    submit()
    #info()
    file_index = tmp_dir / f'index.html'
    save_html(file_index)

    for center in centers:
        link = parse_index(file_index, center)
        if link is False:
            continue

        file_center_AMHS = tmp_dir / f'{center}_AMHS.html'
        file_center_AFTN = tmp_dir / f'{center}_AFTN.html'

        browser.go(site + link[0])
        save_html(file_center_AMHS)
        browser.go(site + link[1])
        save_html(file_center_AFTN)

        parse(file_center_AMHS, center)
        parse(file_center_AFTN, center)

def parse_index(file_index, center):
    with open(file_index, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    try:
        href_actual = soup.find(name='a', text=re.compile('Просмотр действующих данных')).get('href')
        href_center = soup.find(name='a', attrs={'href': re.compile(href_actual)}, text=re.compile(center)).get('href')
        href_center = re.sub(f'{href_actual}\?', '', href_center)
        href_amhs = soup.find(name='a', attrs={'href': re.compile(href_center)}, text=re.compile('AMHS')).get('href')
        href_aftn = soup.find(name='a', attrs={'href': re.compile(href_center)}, text=re.compile('AFTN')).get('href')
    except Exception:
        return False

    return href_amhs, href_aftn

def parse(file_center, center):
    """ Parse HTML page for table data
    """
    with open(file_center, 'r', encoding='utf-8') as read:
        soup = BeautifulSoup(read, 'html.parser')
        if 'AMHS' in file_center.name:
            condition = 'AMHS'
        elif 'AFTN' in file_center.name:
            condition = 'AFTN'
        else:
            return False

        data = _parse_soup(soup, condition)
        populate_centers(data[1], center)
        populate_aftn_amhs(data[0], center, condition)

        #if len(data) == 0:
        #    print(file_center)
        #populate_models(data, index_page)

def populate_centers(data, center):
    import routes
    target_class = getattr(routes.models, 'Center')

    if not target_class.objects.filter(center=center).exists():
        fields_dict = {'center': center,
                       'name': data}
        row_create = target_class.objects.create(**fields_dict)
        row_create.save()

def populate_aftn_amhs(data, center, condition):
    import routes
    center_class = getattr(routes.models, 'Center')
    if center_class.objects.filter(center=center).exists():
        center_ref = center_class.objects.get(center=center)
    else:
        return False
    for fields in data:
        if condition == 'AMHS':
            target_class = getattr(routes.models, 'Amhs')
            fields_dict = {'center': center_ref,
                        'prmd': fields[0],
                        'o': fields[1],
                        'ou': fields[2],
                        'route': fields[3],
                        'route_mtcu': fields[4],
                        'route_res': fields[5],
                        'route_res_mtcu': fields[6],
                        'aftn': fields[7],
                        'country': fields[8]}
        else:
            target_class = getattr(routes.models, 'Aftn')
            fields_dict = {'center': center_ref,
                        'aftn': fields[0],
                        'route': fields[1],
                        'route_res': fields[2]}

        if not target_class.objects.filter(aftn=fields_dict.get('aftn')).filter(center=center_ref).exists():
            row_create = target_class.objects.create(**fields_dict)
            row_create.save()

def _parse_soup(soup, condition):
    """ Parse table for specify index page.
        Return rows data of the table
    """
    name = soup.find(name='h2').text
    table_soup = BeautifulSoup(str(soup.find_all('tbody')), 'html.parser')
    tr_list = table_soup.find_all('tr')
    td_data_list = _parse_rows(tr_list, condition)

    return td_data_list, name

def _parse_rows(tr_list, condition):
    td_data = []
    
    for tr in tr_list:
        td_list = BeautifulSoup(str(tr), 'html.parser').find_all('td')
        dict_parse_td = _parse_table_data(td_list, condition)
        
        if condition == 'AMHS':
            prmd = dict_parse_td['prmd']
            o = dict_parse_td['o']
            ou = dict_parse_td['ou']
            route = dict_parse_td['route']
            route_mtcu = dict_parse_td['route_mtcu']
            route_res = dict_parse_td['route_res']
            route_res_mtcu = dict_parse_td['route_res_mtcu']
            aftn = dict_parse_td['aftn']
            country = dict_parse_td['country']
        else:
            route = dict_parse_td['route']
            route_res = dict_parse_td['route_res']
            aftn = dict_parse_td['aftn']

        for a in aftn.split(' '):
            if a == '':
                continue
            if condition == 'AMHS':
                td_data.append([prmd,
                                o,
                                ou,
                                route,
                                route_mtcu,
                                route_res,
                                route_res_mtcu,
                                a,
                                country])
            else:
                td_data.append([a,
                                route,
                                route_res])

    return td_data

def _parse_table_data(td_list, condition):
    """ Result of parse row is dir:
        prmd, o, ou, route, route_mtcu, route_res, route_res_mtcu, aftn, country (for AMHS)
        aftn, route, route_res (for AFTN)
    """
    result = {'prmd': '',
              'o': '',
              'ou': '',
              'route': '',
              'route_mtcu': False,
              'route_res': '',
              'route_res_mtcu': False,
              'aftn': '',
              'country': ''}
    if condition == 'AMHS':
        result['prmd'] = str(td_list[2].text).strip()
        result['o'] = str(td_list[3].text).strip()
        result['ou'] = str(td_list[4].text).strip()
        result['route'] = str(td_list[5].text).strip()
        result['route_mtcu'] = True if str(td_list[6].text).strip().upper() == 'Y' else False
        route_res = str(td_list[7].text).strip()
        if route_res.find('(') != -1:
            route_res = route_res[1:-1]    
        result['route_res'] = route_res
        result['route_mtcu'] = True if str(td_list[8].text).strip().upper() == 'Y' else False
        result['aftn'] = str(td_list[9].text).strip()
        result['country'] = str(td_list[10].text).strip()
    elif condition == 'AFTN':
        result['aftn'] = str(td_list[0].text).strip()
        result['route'] = str(td_list[1].text).strip()
        result['route_res'] = str(td_list[2].text).strip()

    return result
    

if __name__ == '__main__': 
    #os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
    #sys.path.append('C:/Users/admin/OneDrive/Документы/GitHubRepo/WebTest/begining')
    #django.setup()
    
    parse_anspd()
    #file_test = f'{os.path.abspath("./")}/begining/backend/tmp/index.html'
    #parse_index(file_test, 'UHHH')
    #parse(f'{os.path.abspath("./")}/begining/backend/tmp/UEEE_AFTN.html', 'UEEE')
    