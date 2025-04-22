import os
import mysql.connector
from dotenv import load_dotenv

# Load .env file
print("📦 Attempting to load .env...")
load_dotenv()

# Show debug info
print("🧪 DB_HOST:", os.getenv("DB_HOST"))
print("🧪 DB_PORT:", os.getenv("DB_PORT"))
print("🧪 DB_USER:", os.getenv("DB_USER"))

# Create DB connection
def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            port=int(os.getenv('DB_PORT'))
        )
    except mysql.connector.Error as err:
        print("❌ Failed to connect to database:", err)
        raise
