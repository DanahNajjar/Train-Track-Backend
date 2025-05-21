import mysql.connector
import os
import logging
from dotenv import load_dotenv

# ✅ Load environment variables from .env.local file
env_file = ".env.local"
if os.environ.get("ENV") == "remote":
    env_file = ".env.remote"

load_dotenv(env_file)

# ✅ Improved and safe DB connection
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.environ.get("DB_HOST"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            database=os.environ.get("DB_NAME"),
            port=int(os.environ.get("DB_PORT", 3306)),
            connection_timeout=10,
            autocommit=True
        )

        if not connection.is_connected():
            connection.reconnect(attempts=3, delay=2)

        return connection

    except mysql.connector.Error as err:
        logging.error(f"❌ Database connection failed: {err}")
        raise
