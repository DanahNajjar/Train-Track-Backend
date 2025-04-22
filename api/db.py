import os
import mysql.connector
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Choose profile
profile = os.getenv("PROFILE", "local")

# Determine DB connection config
if profile == "cloud":
    host = os.getenv("CLOUD_DB_HOST")
    port = int(os.getenv("CLOUD_DB_PORT"))
    user = os.getenv("CLOUD_DB_USER")
    password = os.getenv("CLOUD_DB_PASSWORD")
    database = os.getenv("CLOUD_DB_NAME")
else:
    host = os.getenv("LOCAL_DB_HOST", "localhost")
    port = int(os.getenv("LOCAL_DB_PORT", 3306))
    user = os.getenv("LOCAL_DB_USER", "root")
    password = os.getenv("LOCAL_DB_PASSWORD", "")
    database = os.getenv("LOCAL_DB_NAME", "expert_system")

def get_db_connection():
    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )
