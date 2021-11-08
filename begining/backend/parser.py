import glob
import pprint
from datetime import date
from bs4 import BeautifulSoup

import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
sys.path.append('/Users/Abysscope/WebTest/begining/')
django.setup()

from aftn_national.models import Correction, LocationIndicator, DesignatorOrg, SymbolsDepartment


def parse(path, index_page):
    """ Parse HTML page for table data
    """
    list_files = glob.glob(f'{path}/{index_page}_*')

    for file in list_files:
        with open(file, 'r', encoding='cp1251') as read:
            soup = BeautifulSoup(read, 'html.parser')
            data = _parse_soup(soup, index_page)
            if len(data) == 0:
                print(file)
                continue
            populate_models(data, index_page)


def populate_models(data, index_page):
    #pprint.pprint(data, width=180)
    import aftn_national
    model_classes = ['Correction', 'LocationIndicator', 'DesignatorOrg', 'SymbolsDepartment']

    if index_page == 4:
        target_class = getattr(aftn_national.models, model_classes[1])
    elif index_page == 5.1:
        target_class = getattr(aftn_national.models, model_classes[1])

    for fields in data:
        if not LocationIndicator.objects.filter(national=fields[0]).exists():
            if not fields[4] == '':
                if not Correction.objects.filter(number=fields[4]).exists():
                    correction_ref = Correction(number=fields[4],
                                                date=None,
                                                header_aftn_message=fields[6])
                    correction_ref.save()
                else:
                    correction_ref = Correction.objects.get(number=fields[4])
            else:
                correction_ref = None
            loc = LocationIndicator.objects.create(
                national=fields[0],
                international=fields[1],
                name=fields[2],
                district_administration=fields[3],
                correction=correction_ref,
                marked=fields[8],
                excluded=fields[9]
            )
            loc.save()

    print(LocationIndicator.objects.all())


def _parse_soup(soup, index_page):
    """ Parse table for specify index page.
        Return rows data of the table
    """
    if index_page == 4:
        width = 680
    elif index_page == 6 or index_page == 5.1:
        width = 718
    elif index_page == 5.2:
        width = 696
    else:
        return None

    table_soup = BeautifulSoup(str(soup.find_all('table', width=width)), 'html.parser')
    tr_list = table_soup.find_all('tr')
    td_data_list = _parse_rows(tr_list, index_page)

    return td_data_list


def _parse_rows(tr_list, index_page):
    td_data = []
    for tr in tr_list:
        td_list = BeautifulSoup(str(tr), 'html.parser').find_all('td')
        if len(td_list) == 11 or (len(td_list) == 7 and index_page == 5.2 and td_list[0]['width'] != '2'):
            dict_parse_td = _parse_table_data(td_list, index_page)

            national = dict_parse_td['national']
            international = dict_parse_td['international']
            name = dict_parse_td['name']
            district_admin = dict_parse_td['district_admin']
            location = dict_parse_td['location']
            correction_number = str()
            correction_date = None
            correction = dict_parse_td['correction']
            correction_message = str()
            marked = False
            excluded = False

            if national == international == '':
                continue

            if international == 'исключен':
                excluded = True
                international = ''

            if not national.find('*') == -1:
                national = national.replace('*', '')
                marked = True

            if correction != '':
                split_corr = correction.split(' ')
                if len(split_corr) < 3:
                    correction_number = split_corr[len(split_corr) - 2]
                    correction = f'{split_corr[len(split_corr) - 1][:6]} {split_corr[len(split_corr) - 1][6:]}'
                else:
                    correction_number = split_corr[len(split_corr) - 3]
                    correction = f'{split_corr[len(split_corr) - 2]} {split_corr[len(split_corr) - 1]}'
                correction_number = correction_number.replace('№', '')

            if index_page == 4 or index_page == 6:
                td_data.append([national,
                                international,
                                name,
                                district_admin,
                                correction_number,
                                correction_date,
                                correction,
                                correction_message,
                                marked,
                                excluded])
            elif index_page == 5.1:
                td_data.append([national,
                                international,
                                name,
                                location,
                                correction_number,
                                correction_date,
                                correction,
                                correction_message,
                                marked,
                                excluded])
            elif index_page == 5.2:
                td_data.append([national,
                                name,
                                correction_number,
                                correction_date,
                                correction,
                                correction_message,
                                marked,
                                excluded])
    return td_data


def _parse_table_data(td_list, index_page):
    """ Result of parse row is dir:
        national,
        international,
        name,
        district_admin(for index 4, 6)
        location(for index 5.1),
        correction
    """
    result = {'national': '',
              'international': '',
              'name': '',
              'district_admin': '',
              'location': '',
              'correction': '', }
    if index_page == 4:
        result['national'] = str(td_list[7].text).strip()
        result['international'] = str(td_list[5].text).strip()
        result['name'] = str(td_list[1].text).strip()
        result['district_admin'] = str(td_list[3].text).strip()
        result['correction'] = str(td_list[9].text).strip()
    elif index_page == 5.1:
        result['national'] = str(td_list[7].text).strip()
        result['international'] = str(td_list[5].text).strip()
        result['name'] = str(td_list[1].text).strip()
        result['location'] = str(td_list[3].text).strip()
        result['correction'] = str(td_list[9].text).strip()
    elif index_page == 5.2:
        result['national'] = str(td_list[3].text).strip()
        result['name'] = str(td_list[1].text).strip()
        result['correction'] = str(td_list[5].text).strip()
    elif index_page == 6:
        result['national'] = str(td_list[1].text).strip()
        result['international'] = str(td_list[2].text).strip()
        result['name'] = str(td_list[5].text).strip()
        result['district_admin'] = str(td_list[7].text).strip()
        result['correction'] = str(td_list[9].text).strip()

    return result


if __name__ == '__main__':
    parse('/Users/Abysscope/Documents/www', 4)
    pass
