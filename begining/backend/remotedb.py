import psycopg2

import os
import sys
from datetime import datetime, timedelta

SQL = "SELECT text FROM archive_{} " \
      "WHERE sender='{}' AND sender_time='{}' AND " \
      "date_time BETWEEN '{} {}' AND '{} {}' " \
      "AND 'УЛЛЛЫФЫЬ'=all(addresses);"


def request_db(aftn_header, date_field):
    from aftn_national.models import ServerDB

    try:
        sender_time, sender = aftn_header.split(' ')
    except ValueError:
        return 'Заполните поле "Строка отправителя"'

    if date_field is None:
        return 'Заполните поле "Дата поправки"'

    archive_date = f'{date_field.year}_{date_field.month}'
    date = f'{date_field.year}-{date_field.month}-{sender_time[:2]}'
    date_time_from = datetime(1, 1, 1, int(sender_time[2:4]), int(sender_time[4:]))
    time_delta = timedelta(minutes=15, seconds=59)
    if not (date_time_from + time_delta).time() > date_time_from.time():
        time_max = datetime(1, 1, 1, 23, 59, 59)
        time_delta = time_max - date_time_from
    date_time_to = date_time_from + time_delta

    for db_host in ServerDB.objects.filter(host='172.20.0.12'):
        db_conn = {'dbname': db_host.dbname,
                   'user': db_host.user,
                   'password': db_host.password,
                   'host': db_host.host,
                   'port': db_host.port
                   }

        result = connect({'sender': sender,
                          'sender_time': sender_time,
                          'archive_date': archive_date,
                          'date': date,
                          'date_time_from': date_time_from.time(),
                          'date_time_to': date_time_to.time()},
                         db_conn)
        print(result)


def connect(param_request, db_conn):
    sql_request = SQL.format(param_request['archive_date'],
                             param_request['sender'],
                             param_request['sender_time'],
                             param_request['date'],
                             param_request['date_time_from'],
                             param_request['date'],
                             param_request['date_time_to']
                             )

    conn = None
    print(sql_request)
    try:
        conn = psycopg2.connect(**db_conn, connect_timeout=1)
        with conn.cursor() as cur:
            cur.execute(sql_request)
            query = cur.fetchone()
            print(query)
            with open('db_query.txt', 'w') as wr:
                wr.write(query[0])
    except (Exception, psycopg2.DatabaseError) as err:
        return err
    finally:
        if conn is not None:
            conn.close()


if __name__ == '__main__':
    sys.path.append('/Users/Abysscope/WebTest/begining/')
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
    import django
    from django.conf import settings

    if not settings.configured:
        django.setup()
    request_db()
