from html.parser import HTMLParser
import codecs
import os
import re
from bs4 import BeautifulSoup

def parse(html_file):
    dirf, namef = os.path.split(html_file)
    write_file = '{}/{}utf.html'.format(dirf, namef.split('.')[0])

    with open(html_file, 'r', encoding='cp1251') as read:
        soup = BeautifulSoup(read, 'html.parser')
        #with open(write_file, 'w', encoding='utf-8') as write:
        #    write.write(read.read())

    #read_file = codecs.decode(bytes(read_file), encoding='utf-8')
    regex = re.compile(r'\s*')
    regex_string = re.compile(r'\s*(\W.*)')
    table_parse = soup.find('table')
    for td in table_parse.find_all('td'):
        td_str = td.text.replace('\n', '')
        #if not regex.fullmatch(td_str):
        print(td_str)

if __name__ == '__main__':
    parse('/Users/Abysscope/Documents/example/4_1.htm')
    pass