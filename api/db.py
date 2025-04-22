import os
import mysql.connector
from dotenv import load_dotenv

# ✅ Load the environment variables
load_dotenv()

# ✅ Connect directly to Railway DB
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
