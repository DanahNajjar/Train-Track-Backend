import os
import mysql.connector
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        print("✅ Connected to database successfully!")
        return connection
    except mysql.connector.Error as err:
        print("❌ Failed to connect to database:", err)
        raise
