import glob
import pprint
from bs4 import BeautifulSoup


def parse(path, index_page):
    """Parse HTML page for table data"""
    list_files = glob.glob(f'{path}/{index_page}*.htm')

    for file in list_files:
        with open(file, 'r', encoding='cp1251') as read:
            soup = BeautifulSoup(read, 'html.parser')
        _parse_soup(soup, index_page)


def _parse_soup(soup, index_page):
    # width='680' for index_page='4', width='718' for index_page='6'
    if index_page == 4:
        table_soup = BeautifulSoup(str(soup.find_all('table', width='680')), 'html.parser')
    elif index_page == 6:
        table_soup = BeautifulSoup(str(soup.find_all('table', width='718')), 'html.parser')
    else:
        return None

    tr_list = table_soup.find_all('tr')
    td_data = []
    for tr in tr_list:
        td_list = BeautifulSoup(str(tr), 'html.parser').find_all('td')
        if len(td_list) == 11:
            list_parse_td = _parse_table_data(td_list, index_page)

            national = list_parse_td[0]
            international = list_parse_td[1]
            item_name = list_parse_td[2]
            district_admin = list_parse_td[3]
            correction_number = str()
            correction_date = None
            correction = list_parse_td[4]
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

            td_data.append([national,
                            international,
                            item_name,
                            district_admin,
                            correction_number,
                            correction_date,
                            correction,
                            correction_message,
                            marked,
                            excluded])

    pprint.pprint(td_data, width=180)


def _parse_table_data(td_list, index_page=4):
    """ Result of parse row is list at sequence:
        national,
        international,
        item_name,
        district_admin,
        correction
    """
    result = []
    if index_page == 4:
        result.append(str(td_list[7].text).strip())
        result.append(str(td_list[5].text).strip())
        result.append(str(td_list[1].text).strip())
        result.append(str(td_list[3].text).strip())
        result.append(str(td_list[9].text).strip())
    elif index_page == 6:
        result.append(str(td_list[1].text).strip())
        result.append(str(td_list[3].text).strip())
        result.append(str(td_list[5].text).strip())
        result.append(str(td_list[7].text).strip())
        result.append(str(td_list[9].text).strip())
    return result


if __name__ == '__main__':
    parse('/Users/Abysscope/Documents/example', 6)
    pass