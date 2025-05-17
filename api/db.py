import pymysql
import os
import logging

def get_db_connection():
    try:
        connection = pymysql.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=int(os.getenv("DB_PORT", 3306)),
            ssl={"ssl": {}},            # ✅ Needed for Railway SSL
            connect_timeout=10
        )
        logging.info("✅ Successfully connected to the database.")
        return connection
    except pymysql.MySQLError as err:
        logging.error(f"❌ Database connection failed: {err}")
        raise
