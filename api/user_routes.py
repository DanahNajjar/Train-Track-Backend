from flask import Blueprint, request, jsonify, current_app
from api.db import get_db_connection
import uuid
import json  
import google.auth.transport.requests
import google.oauth2.id_token

user_routes = Blueprint('user_routes', __name__)

# ✅ 1. Google Login
@user_routes.route('/google-login', methods=['POST'])
def google_login():
    try:
        data = request.get_json()
        id_token = data.get("id_token")
        if not id_token:
            return jsonify({"success": False, "message": "Missing ID token."}), 400

        request_adapter = google.auth.transport.requests.Request()
        decoded_token = google.oauth2.id_token.verify_oauth2_token(id_token, request_adapter)

        user_email = decoded_token.get("email")
        full_name = decoded_token.get("name")
        google_user_id = decoded_token.get("sub")

        if not user_email or not full_name:
            return jsonify({"success": False, "message": "Incomplete Google user info."}), 400

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Check for existing user
        cursor.execute("SELECT id FROM users WHERE email = %s", (user_email,))
        user = cursor.fetchone()

        if user:
            user_id = user["id"]
        else:
            # ✅ Create new user
            cursor.execute("""
                INSERT INTO users (google_user_id, full_name, email)
                VALUES (%s, %s, %s)
            """, (google_user_id, full_name, user_email))
            connection.commit()
            user_id = cursor.lastrowid

        return jsonify({
            "success": True,
            "user_id": user_id,
            "full_name": full_name,
            "email": user_email
        }), 200

    except ValueError as ve:
        return jsonify({"success": False, "message": "Invalid Google token."}), 400

    except Exception as e:
        current_app.logger.error(f"❌ Login error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


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
