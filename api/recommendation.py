# api/recommendation.py

from flask import Blueprint, request, jsonify
import mysql.connector

recommendation_routes = Blueprint('recommendation', __name__)

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Traintrack@2025",
        database="expert_system"
    )

@recommendation_routes.route('/recommendations', methods=['POST'])
def get_recommendations():
    # ⬇️ Paste your full /recommendations logic here
    ...
