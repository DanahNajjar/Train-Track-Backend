import os
import mysql.connector

def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv('MYSQL_HOST'),
            user=os.getenv('MYSQL_USER'),
            password=os.getenv('MYSQL_PASSWORD'),
            database=os.getenv('MYSQL_DATABASE'),
            port=int(os.getenv('MYSQL_PORT'))
        )
    except mysql.connector.Error as err:
        print("❌ Failed to connect to database:", err)
        raise
