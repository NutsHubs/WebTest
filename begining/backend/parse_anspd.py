import os
import sys
import django
import re
import json
import datetime
from pathlib import Path

from twill.commands import *
from twill import browser
from bs4 import BeautifulSoup

site = 'https://anspd.ru'
centers = ['UIII', 'UWWW', 'UEEE', 'ULLL', 'UNKL', 'UNNT', 'URRR', 'USSV', 'USTU', 'UUUU', 'UUYY', 'UHMM', 'UHPP', 'UHHH']
base_dir = Path(__file__)
tmp_dir = Path(f'{Path(__file__).resolve().parent}/tmp/')
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
    file_index = tmp_dir / 'index.html'
    save_html(str(file_index))

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
    
    add_data = [] #added aftns
    change_data = {} #changed fields for each aftn
    recieved_data = [] #recieved aftns

    for fields in data:
        amhs_value = ''
        if condition == 'AMHS':
            target_class = getattr(routes.models, 'Amhs')
            fields_dict = {'center': center_ref,
                        'amhs': fields[0],
                        'route': fields[1],
                        'route_mtcu': fields[2],
                        'route_res': fields[3],
                        'route_res_mtcu': fields[4],
                        'aftn': fields[5],
                        'country': fields[6]}
            target_class_filter = target_class.objects.filter(center=center_ref, 
                                                              aftn=fields_dict['aftn'],
                                                              amhs=fields_dict['amhs'])
            amhs_value = fields_dict['amhs']
            recieved_data.append((fields_dict['aftn'], fields_dict['amhs']))
        else:
            target_class = getattr(routes.models, 'Aftn')
            fields_dict = {'center': center_ref,
                        'aftn': fields[0],
                        'route': fields[1],
                        'route_res': fields[2]}
            target_class_filter = target_class.objects.filter(center=center_ref,
                                                              aftn=fields_dict['aftn'])
            recieved_data.append(fields_dict['aftn'])
            
        aftn_value = fields_dict['aftn']

        if target_class_filter.exists():
            target_values = list(target_class_filter.values())[0]
            for k, v in fields_dict.items(): 
                if k == 'center':
                    continue

                if target_values[k] != v:
                    value = target_values[k]
                    new_value = v
                    key_name = target_class._meta.get_field(k).verbose_name

                    #for add humanable note in list of changes
                    if k == 'route' or k == 'route_res':
                        key_name = f'{key_name} {condition}'
                    elif k == 'route_mtcu' or k == 'route_res_mtcu':
                        new_value = 'Да' if v else 'Нет'
                        value = 'Да' if value else 'Нет'
                    
                    change_string = f'{key_name}: {value} >>> {new_value}'

                    if aftn_value:
                        if aftn_value in change_data.keys():
                            change_data[aftn_value] += [change_string]
                        else:
                            change_data[aftn_value] = [change_string]
                    else:
                        if amhs_value in change_data.keys():
                            change_data[amhs_value] += [change_string]
                        else:
                            change_data[amhs_value] = [change_string]

                    target_class_filter.update(**{k: v})
        else: 
            if aftn_value and amhs_value:
                add_value = f'{amhs_value} для {aftn_value}'
            elif aftn_value:
                add_value = f'{aftn_value}'
            elif amhs_value:
                add_value = f'{amhs_value}'
            
            add_data.append(add_value)
            row_create = target_class.objects.create(**fields_dict)
            row_create.save()
    
    #TO DO for amhs and aftn fields 
    if condition == 'AMHS':
        current_data = list(target_class.objects.filter(center=center_ref).values_list('aftn', 'amhs'))
    else:
        current_data = list(target_class.objects.filter(center=center_ref).values_list('aftn', flat=True))
    deleted_data = list(set(current_data) - set(recieved_data))

    for deleted in deleted_data:
        if condition == 'AMHS':
            target_class.objects.filter(aftn=deleted[0], amhs=deleted[1], center=center_ref).delete()
        else:
            target_class.objects.filter(aftn=deleted[0], center=center_ref).delete()

    if add_data or change_data or deleted_data:
        history_class = getattr(routes.models, 'History')

        try:
            history_date = history_class.objects.all().first().date.strftime('%d %B %Y')
            if datetime.datetime.now().strftime('%d %B %Y') != history_date:
                history_class.objects.all().delete()
        except:
            pass

        for add in add_data:
            row_create = history_class.objects.create(**{'center': center_ref,
                                                         'aftn': add,
                                                         'history_type': 1})
            row_create.save()
        
        for key_aftn, values_list in change_data.items():
            row_create = history_class.objects.create(**{'center': center_ref,
                                                         'aftn': key_aftn,
                                                         'history_type': 2,
                                                         'notes': '\n'.join(values_list)})
            row_create.save()

        for deleted in deleted_data:
            if condition == 'AMHS':
                del_value = f'{deleted[1]} для {deleted[0]}'
            else:
                del_value = f'{deleted[0]}'
            row_create = history_class.objects.create(**{'center': center_ref,
                                                         'aftn': del_value,
                                                         'history_type': 3})
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
            amhs = dict_parse_td['amhs']
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
            '''if a == '':
                continue'''
            if condition == 'AMHS':
                td_data.append([amhs,
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
    result = {'amhs': '',
              'route': '',
              'route_mtcu': False,
              'route_res': '',
              'route_res_mtcu': False,
              'aftn': '',
              'country': ''}
    if condition == 'AMHS':
        amhs = f'/PRMD={str(td_list[2].text).strip()}/'
        o = str(td_list[3].text).strip()
        ou = str(td_list[4].text).strip()
        if o :
            amhs = f'{amhs}O={o}/'
            if ou :
                amhs = f'{amhs}OU={ou}/'
        result['amhs'] = amhs
        result['route'] = str(td_list[5].text).strip()
        result['route_mtcu'] = True if str(td_list[6].text).strip().upper() == 'Y' else False
        route_res = str(td_list[7].text).strip()
        if route_res.find('(') != -1:
            route_res = route_res[1:-1]    
        result['route_res'] = route_res
        result['route_res_mtcu'] = True if str(td_list[8].text).strip().upper() == 'Y' else False
        result['aftn'] = str(td_list[9].text).strip().replace('&nbsp', '')
        result['country'] = str(td_list[10].text).strip()
    elif condition == 'AFTN':
        aftn = str(td_list[0].text).strip()
        if aftn.find('*') != -1:
            aftn = aftn.replace('*', '')
        result['aftn'] = aftn
        route = str(td_list[1].text).strip()
        if route.find('(') != -1:
            route = route[1:-1]
        result['route'] = route
        route_res = str(td_list[2].text).strip()
        if route_res.find('(') != -1:
            route_res = route_res[1:-1]
        result['route_res'] = route_res

    return result
    

if __name__ == '__main__': 
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
    #sys.path.append('C:/Users/admin/OneDrive/Документы/GitHubRepo/WebTest/begining')
    sys.path.append(f'{Path(__file__).resolve().parent.parent}')
    django.setup()
    
    parse_anspd()
    #file_test = tmp_dir / 'UUUU_AMHS.html'
    #parse(file_test, 'UUUU')
    #parse(f'{os.path.abspath("./")}/begining/backend/tmp/UEEE_AFTN.html', 'UEEE')
    