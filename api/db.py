import pymysql
import os

def get_db_connection():
    try:
        return pymysql.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=int(os.getenv("DB_PORT", 3306)),
            ssl={"ssl": {}},
            connect_timeout=10
        )
    except pymysql.MySQLError as err:
        print(f"❌ PyMySQL connection failed: {err}")
        raise
