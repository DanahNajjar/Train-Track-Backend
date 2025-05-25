from flask import Blueprint, request, jsonify, current_app
from api.db import get_db_connection
import uuid
import json  
import google.auth.transport.requests
import google.oauth2.id_token

user_routes = Blueprint('user_routes', __name__)

# ✅ 1. Google Login
@user_routes.route('/user/google-login', methods=["GET"])
def google_login():
    try:
        id_token = request.args.get("credential")  # ✅ get from URL param

        if not id_token:
            return jsonify({"success": False, "message": "Missing token"}), 400

        # ✅ (Optional) verify token using Google libraries
        # user_info = verify_google_token(id_token)  # if you implement this

        # Simulate a user ID for now
        user_id = "google_" + id_token[:10]  # just mock
        session['user_id'] = user_id

        return redirect("https://train-track-frontend.onrender.com/traintrack/start")

    except Exception as e:
        print(f"❌ Google login error: {e}")
        return jsonify({"success": False, "message": "Server error"}), 500

# ✅ 2. Guest ID Generator
@user_routes.route('/guest', methods=['GET'])
def generate_guest_user():
    guest_id = f"guest_{uuid.uuid4().hex[:8]}"
    return jsonify({
        "success": True,
        "user_id": guest_id
    }), 200
    
@user_routes.route('/results/<user_id>', methods=['GET'])
def get_user_results(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, submission_data, result_data, submitted_at
            FROM user_results
            WHERE user_id = %s
            ORDER BY submitted_at DESC
        """, (user_id,))

        results = cursor.fetchall()

        return jsonify({
            "success": True,
            "trials": results
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection and connection.is_connected():
            connection.close()

@user_routes.route('/results', methods=['POST'])
def save_user_results():
    connection = None
    try:
        data = request.get_json()

        # ✅ Extract values
        user_id = data.get("user_id")
        submission_data = data.get("submission_data")
        result_data = data.get("result_data")

        # ✅ Validate
        if not user_id or not submission_data or not result_data:
            return jsonify({
                "success": False,
                "message": "Missing user_id, submission_data or result_data"
            }), 400

        # ✅ Convert Python dicts/lists to JSON strings
        submission_json = json.dumps(submission_data)
        result_json = json.dumps(result_data)

        # ✅ Connect and insert
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO user_results (user_id, submission_data, result_data)
            VALUES (%s, %s, %s)
        """, (user_id, submission_json, result_json))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "✅ Result saved successfully"
        }), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error saving user result: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:
        if connection and connection.is_connected():
            connection.close()

@user_routes.route('/profile/<user_id>', methods=['GET'])
def get_user_profile(user_id):
    try:
        # ✅ Handle guest users
        if user_id.startswith("guest_"):
            return jsonify({
                "success": True,
                "user": {
                    "id": user_id,
                    "full_name": "Guest User",
                    "email": None,
                    "registration_date": None,
                    "role": "guest"
                },
                "guest": True
            }), 200

        # ✅ Handle real users from DB
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, full_name, email, registration_date, role
            FROM users
            WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        return jsonify({
            "success": True,
            "user": user,
            "guest": False
        }), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error fetching profile: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if 'connection' in locals() and connection and connection.is_connected():
            connection.close()

@user_routes.route('/results/<int:trial_id>', methods=['DELETE'])
def delete_user_result(trial_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("DELETE FROM user_results WHERE id = %s", (trial_id,))
        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "Result not found"}), 404

        return jsonify({"success": True, "message": "✅ Trial deleted"}), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error deleting result: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection and connection.is_connected():
            connection.close()
