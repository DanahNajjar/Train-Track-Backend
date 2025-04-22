import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()
profile = os.getenv("PROFILE", "local")

if profile == "cloud":
    host = os.getenv("CLOUD_DB_HOST")
    port = int(os.getenv("CLOUD_DB_PORT"))
    user = os.getenv("CLOUD_DB_USER")
    password = os.getenv("CLOUD_DB_PASSWORD")
    database = os.getenv("CLOUD_DB_NAME")
else:
    host = os.getenv("LOCAL_DB_HOST")
    port = int(os.getenv("LOCAL_DB_PORT"))
    user = os.getenv("LOCAL_DB_USER")
    password = os.getenv("LOCAL_DB_PASSWORD")
    database = os.getenv("LOCAL_DB_NAME")

def get_db_connection():
    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )
