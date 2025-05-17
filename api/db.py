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
            ssl_disabled=False,            # ✅ Required for Render + Railway
            connection_timeout=10,         # ⏳ Prevent timeout errors
            use_pure=True                  # ✅ Use Python connector directly
        )
    except mysql.connector.Error as err:
        print(f"❌ Database connection failed: {err}")
        raise
