import psycopg2
from psycopg2 import OperationalError


def create_conn():
    conn = None
    try:
        conn = psycopg2.connect(
            database="sx5-db",
            user="lukasz",
            password="grgnajgnak1231241452kgaknfd",
            host="localhost",
            port="5432",
        )
        print("Connection to PostgreSQL DB successful")
    except OperationalError as e:
        print(f"The error '{e}' occurred")
    return conn


connection = create_conn()
