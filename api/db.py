import mysql.connector
import os

def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=int(os.getenv("DB_PORT", 3306)),
            ssl_disabled=False  # 🔐 Enable SSL for Railway external access
        )
    except mysql.connector.Error as err:
        print(f"❌ Database connection failed: {err}")
        raise
