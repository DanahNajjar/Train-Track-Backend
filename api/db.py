import os
 import mysql.connector
 from dotenv import load_dotenv
 
 # Load .env variables
 print("📦 Attempting to load .env...")
 load_dotenv()
 
 print("🧪 DB_HOST:", os.getenv("DB_HOST"))
 print("🧪 DB_PORT:", os.getenv("DB_PORT"))
 print("🧪 DB_USER:", os.getenv("DB_USER"))
 
 def get_db_connection():
     try:
         return pymysql.connect(
             host=os.getenv('MYSQL_HOST'),
             user=os.getenv('MYSQL_USER'),
             password=os.getenv('MYSQL_PASSWORD'),
             db=os.getenv('MYSQL_DATABASE'),
             port=int(os.getenv('MYSQL_PORT')),
             cursorclass=pymysql.cursors.DictCursor
         )
     except pymysql.MySQLError as e:
         print("❌ Database connection failed:", e)
         raise
     return mysql.connector.connect(
         host=os.getenv('DB_HOST'),
         user=os.getenv('DB_USER'),
         password=os.getenv('DB_PASSWORD'),
         database=os.getenv('DB_NAME'),
         port=int(os.getenv('DB_PORT'))
     )
