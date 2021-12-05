import psycopg2
"""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "begining.settings")
sys.path.append('/Users/Abysscope/WebTest/begining/')
django.setup()
"""
from aftn_national import models


def request_db(dbconn=''):
    print(dbconn)

    db_queryset = models.ServerDB.objects.all()
    for db in db_queryset:
        print(db)

    try:
        conn = psycopg2.connect(dbconn)
    except Exception:
        print('error')
        return None

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute()
    except Exception:
        print('error')
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    request_db()


