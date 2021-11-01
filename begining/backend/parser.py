from html.parser import HTMLParser
import codecs
import os
import re
from bs4 import BeautifulSoup

def parse(html_file='/Users/Abysscope/Documents/example/4_1.htm'):
    dirf, namef = os.path.split(html_file)
    write_file = '{}/{}utf.html'.format(dirf, namef.split('.')[0])

    with open(html_file, 'r', encoding='cp1251') as read:
        soup = BeautifulSoup(read, 'html.parser')
        #with open(write_file, 'w', encoding='utf-8') as write:
        #    write.write(read.read())

    #read_file = codecs.decode(bytes(read_file), encoding='utf-8')
    regex = re.compile(r'\s*')
    regex_string = re.compile(r'\s*(\W.*)')
    soup_table = BeautifulSoup(str(soup.find_all('table', width='680')), 'html.parser')
    tr_list = soup_table.find_all('tr')

    for tr in tr_list:
        #td_str = td.text.replace('\n', '')
        #if not regex.fullmatch(td_str):
        td_list = BeautifulSoup(str(tr), 'html.parser').find_all('td')
        if len(td_list) == 11:
            for td in td_list:
                if not len(str(td.text).strip()) == 0:
                    print(str(td.text).strip())

def has_attr_in_tag(tag):
    return tag.has_attr("width") and tag.has_attr("")

if __name__ == '__main__':
    parse('/Users/Abysscope/Documents/example/4_1.htm')
    pass