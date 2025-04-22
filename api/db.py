import os
import mysql.connector

# Render injects these directly into env variables
host = os.getenv("MYSQL_HOST")              # e.g. shuttle.proxy.rlwy.net
port = int(os.getenv("MYSQL_PORT"))         # e.g. 59084
user = os.getenv("MYSQL_USER")              # root
password = os.getenv("MYSQL_PASSWORD")      # your Render DB password
database = os.getenv("MYSQL_DATABASE")      # railway

def get_db_connection():
    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )
