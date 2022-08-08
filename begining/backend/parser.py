import glob
import pprint
import re
import csv
from datetime import date
from bs4 import BeautifulSoup

import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
sys.path.append('/Users/Abysscope/WebTest/begining/')
django.setup()


def parse_csv(path, index_page=None):
    """ Parse csv file """
    with open(path, 'r', newline='\r\n', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        import aftn_national
        target_class = getattr(aftn_national.models, 'AnnexFour')

        for row in reader:
            item = row[0]
            com_center = row[1]
            replaced_aftn = row[2]
            new_aftn = row[3]
            name = row[4]

            if len(item) > 0:
                previous_item = item
            else:
                item = previous_item

            if len(com_center) > 0:
                previous_com = com_center
            else:
                com_center = previous_com

            fields_dict = {'item': item,
                           'com_center': com_center,
                           'replaced_aftn': replaced_aftn,
                           'new_aftn': new_aftn,
                           'name': name}

            obj_is = target_class.objects.filter(item__exact=item,
                                                 com_center__exact=com_center,
                                                 replaced_aftn__exact=replaced_aftn,
                                                 new_aftn__exact=new_aftn,
                                                 name__exact=name
                                                 ).exists()
            if not obj_is:
                row_create = target_class.objects.create(**fields_dict)
                row_create.save()


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
    # pprint.pprint(data, width=180)
    import aftn_national
    model_classes = ['Correction', 'LocationIndicator', 'DesignatorOrg', 'SymbolsDepartment']

    if index_page == 4:
        target_class = getattr(aftn_national.models, model_classes[1])
    elif index_page == 5.1:
        target_class = getattr(aftn_national.models, model_classes[2])
    elif index_page == 5.2:
        target_class = getattr(aftn_national.models, model_classes[3])
    else:
        return False

    correction_class = getattr(aftn_national.models, model_classes[0])
    location_class = getattr(aftn_national.models, model_classes[1])
    list_error = []

    for fields in data:
        if not (fields[0] == '' or target_class.objects.filter(national=fields[0]).exists()):
            length = len(fields)
            corr_number = fields[length - 6]
            if corr_number == '':
                correction_ref = None
            else:
                if correction_class.objects.filter(number=corr_number).exists():
                    correction_ref = correction_class.objects.get(number=corr_number)
                else:
                    correction_ref = correction_class(number=int(corr_number),
                                                      date=None,
                                                      header_aftn_message=fields[length - 4])
                    correction_ref.save()

            fields_dict = {'national': fields[0],
                           'correction': correction_ref,
                           'marked': fields[length - 2],
                           'excluded': fields[length - 1]}

            if index_page == 4 or index_page == 5.1:
                fields_dict['international'] = fields[1]
                fields_dict['name'] = fields[2]
                if index_page == 4:
                    fields_dict['district_administration'] = fields[3]
                else:  # index_page = 5.1
                    if fields[3] == '':
                        location_ref = None
                    elif location_class.objects.filter(national=fields[3]).exists():
                        location_ref = location_class.objects.get(national=fields[3])
                    else:
                        location_ref = None
                        list_error.append(f'Unknown national\nFields: {fields}\n Index page: {index_page}\n\n')
                    fields_dict['location'] = location_ref
            elif index_page == 5.2:
                fields_dict['name'] = fields[1]
            else:
                return False

            row_create = target_class.objects.create(**fields_dict)
            row_create.save()
        else:  # not exists or repeat 'national' in target class
            list_error.append(f'Not exists or repeat national\nFields: {fields}\n Index page: {index_page}\n\n')

    with open('error.txt', 'a') as wr:
        for string in list_error:
            wr.write(string)
    # pprint.pprint(target_class.objects.all())


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

            regex = re.compile(r'\W+(\d+) (\d{6}) (\S{8})')
            match_groups = regex.fullmatch(correction)
            if match_groups is not None:
                correction_number = match_groups.group(1)
                correction = f'{match_groups.group(2)} {match_groups.group(3)}'
            else:
                correction = str()

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
    # parse('/Users/Abysscope/Documents/www/indexes', 5.2)
    parse_csv('/Users/Abysscope/Downloads/annex_4.csv')
    pass
