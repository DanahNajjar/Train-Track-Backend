from flask import Blueprint, request, jsonify
from api.db import get_db_connection

recommendation_routes = Blueprint('recommendation', __name__)

@recommendation_routes.route('/recommendations', methods=['POST'])
def get_recommendations():
    data = request.get_json()
    
    # Example expected input structure:
    # {
    #   "major_id": 1,
    #   "subjects": [...],
    #   "technical_skills": [...],
    #   "non_technical_skills": [...],
    #   "preferences": {...}
    # }

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ⬇️ Placeholder: replace this with your real recommendation logic
        cursor.execute("SELECT * FROM positions LIMIT 3")
        sample_positions = cursor.fetchall()

        connection.close()

        return jsonify({
            "success": True,
            "recommendations": sample_positions
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
