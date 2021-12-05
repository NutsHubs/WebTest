import psycopg2


def request_db():
    conn = psycopg2.connect('')
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute()
    finally:
        conn.close()


if __name__ == '__main__':
    request_db()


