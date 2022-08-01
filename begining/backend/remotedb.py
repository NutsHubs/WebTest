import psycopg2

import os
import sys
from datetime import datetime, timedelta

SQL = "SELECT text FROM archive_{} " \
      "WHERE sender='{}' AND sender_time='{}' AND " \
      "date_time BETWEEN '{}' AND '{}' " \
      "AND 'УЛЛЛЫФЫЬ'=all(addresses);"


def request_db(aftn_header, date_field: datetime):
    from aftn_national.models import ServerDB
    error = True

    try:
        sender_time, sender = aftn_header.split(' ')
    except ValueError:
        return 'Заполните поле "Строка отправителя"', error

    if date_field is None:
        return 'Заполните поле "Дата поправки"', error

    archive_date, date_time_from, date_time_to = get_date(sender_time, date_field)

    request_text = 'Not records of servers in DB.', error
    for db_host in ServerDB.objects.all():
        db_conn = {'dbname': db_host.dbname,
                   'user': db_host.user,
                   'password': db_host.password,
                   'host': db_host.host,
                   'port': db_host.port
                   }

        request_text = connect({'archive_date': archive_date,
                                'sender': sender,
                                'sender_time': sender_time,
                                'date_time_from': date_time_from,
                                'date_time_to': date_time_to},
                               db_conn)

        if not request_text[1]:
            return text_strip_verify(request_text[0])
        elif str(request_text[0]).find('timeout expired'):
            continue
        else:
            break
    return request_text


def connect(param_request, db_conn):
    sql_request = SQL.format(param_request['archive_date'],
                             param_request['sender'],
                             param_request['sender_time'],
                             param_request['date_time_from'],
                             param_request['date_time_to']
                             )

    conn = None
    error = False
    try:
        conn = psycopg2.connect(**db_conn, connect_timeout=1)
        with conn.cursor() as cur:
            cur.execute(sql_request)
            query = cur.fetchone()[0]
    except (Exception, psycopg2.DatabaseError) as err:
        query = err
        error = True
    finally:
        if conn is not None:
            conn.close()
    return query, error


def get_date(sender_time, date_field: datetime):
    archive_date = f'{date_field.year}_%02d' % date_field.month
    date_time_from = datetime(date_field.year,
                              date_field.month,
                              day=int(sender_time[:2]),
                              hour=int(sender_time[2:4]),
                              minute=int(sender_time[4:]))
    time_delta = date_time_from.replace(hour=23, minute=59, second=59) - date_time_from
    if time_delta > timedelta(minutes=14, seconds=59):
        date_time_to = date_time_from + timedelta(minutes=14, seconds=59)
    else:
        date_time_to = date_time_from + time_delta

    return archive_date, date_time_from, date_time_to


def text_strip_verify(text_raw: str):
    text_strip = "".join([line for line in text_raw.strip().splitlines(True) if line.strip()])
    if len(text_strip) <= 1800:
        return text_strip, False
    else:
        return 'Текст длиннее 1800 знаков', True


if __name__ == '__main__':
    sys.path.append('/Users/Abysscope/WebTest/begining/')
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
    import django
    from django.conf import settings

    if not settings.configured:
        django.setup()
    request_db('080638 ууууясдт', datetime(2021, 9, 8))
    with open('/Users/Abysscope/WebTest/begining/db_query.txt', 'r') as r:
        text = r.read()
    text_strip_verify(text)
