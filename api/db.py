import pymysql
import os

def get_db_connection():
    try:
        connection = pymysql.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=int(os.getenv("DB_PORT", 3306)),
            ssl={"ssl": {}},  # ✅ Required for Railway
            connect_timeout=10
        )
        return connection
    except pymysql.MySQLError as err:
        print(f"❌ Database connection failed: {err}")
        raise
