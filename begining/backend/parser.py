from html.parser import HTMLParser
import codecs
import os
import pprint
from bs4 import BeautifulSoup


def parse(html_file='/Users/Abysscope/Documents/example/4_1.htm'):
    """Parse HTML page for table data"""

    with open(html_file, 'r', encoding='cp1251') as read:
        soup = BeautifulSoup(read, 'html.parser')

    table_soup = BeautifulSoup(str(soup.find_all('table', width='718')), 'html.parser') # width='680':page '4' width='718':page '6'
    tr_list = table_soup.find_all('tr')
    td_data = []
    for tr in tr_list:
        td_list = BeautifulSoup(str(tr), 'html.parser').find_all('td')
        if len(td_list) == 11 and not (str(td_list[3].text).strip() ==
                            str(td_list[5].text).strip() ==
                            str(td_list[7].text).strip() ==
                            str(td_list[9].text).strip() == ''):
            td_data.append([str(td_list[1].text).strip(),
                            str(td_list[3].text).strip(),
                            str(td_list[5].text).strip(),
                            str(td_list[7].text).strip(),
                            str(td_list[9].text).strip()])
    pprint.pprint(td_data)


if __name__ == '__main__':
    parse('/Users/Abysscope/Documents/example/6_all.htm')
    pass