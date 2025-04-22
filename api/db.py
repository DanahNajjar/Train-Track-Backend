import os
import mysql.connector

# This reads environment variables directly (Render & Railway)
host = os.getenv("MYSQL_HOST")
port = int(os.getenv("MYSQL_PORT", 3306))
user = os.getenv("MYSQL_USER")
password = os.getenv("MYSQL_PASSWORD")
database = os.getenv("MYSQL_DATABASE")

def get_db_connection():
    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )
