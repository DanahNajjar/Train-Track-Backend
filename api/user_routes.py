from flask import Blueprint, request, jsonify, current_app, session, redirect
from api.db import get_db_connection
import os
import uuid
import json
import google.auth.transport.requests
import google.oauth2.id_token

user_routes = Blueprint('user_routes', __name__)

# ✅ 1. Google Login (Secure & Clean)
@user_routes.route('/google-login', methods=['GET', 'POST'])
def google_login():
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests

        token = request.form.get("credential") or request.args.get("credential")
        if not token:
            return jsonify({"success": False, "message": "Missing token"}), 400

        CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
        id_info = id_token.verify_oauth2_token(token, requests.Request(), CLIENT_ID)

        # ✅ Extract user info from Google
        google_user_id = id_info['sub']
        full_name = id_info.get('name', '')
        email = id_info.get('email', '')

        session['user_id'] = google_user_id

        connection = get_db_connection()
        cursor = connection.cursor()

        # ✅ Insert only if user is new
        cursor.execute("SELECT id FROM users WHERE google_user_id = %s", (google_user_id,))
        result = cursor.fetchone()
        if not result:
            cursor.execute("""
                INSERT INTO users (google_user_id, full_name, email)
                VALUES (%s, %s, %s)
            """, (google_user_id, full_name, email))
            connection.commit()

        return redirect(f"http://localhost:8000/profile?user_id={google_user_id}")

    except ValueError:
        return jsonify({"success": False, "message": "Invalid token"}), 401

    except Exception as e:
        current_app.logger.error(f"❌ Google login error: {e}")
        return jsonify({"success": False, "message": "Server error"}), 500

    finally:
        if 'connection' in locals() and connection and connection.is_connected():
            connection.close()

# ✅ 2. Guest ID Generator
@user_routes.route('/guest', methods=['GET'])
def generate_guest_user():
    guest_id = f"guest_{uuid.uuid4().hex[:8]}"
    return jsonify({
        "success": True,
        "user_id": guest_id
    }), 200

# ✅ 3. Save User Results
@user_routes.route('/results', methods=['POST'])
def save_user_results():
    connection = None
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        submission_data = data.get("submission_data")
        result_data = data.get("result_data")

        if not user_id or not submission_data or not result_data:
            return jsonify({
                "success": False,
                "message": "Missing user_id, submission_data or result_data"
            }), 400

        # ✅ PATCH missing percentages if needed
        if "recommended_position" in result_data:
            result_data["subject_fit_percentage"] = result_data.get("subject_fit_percentage", 75.0)
            result_data["technical_skill_fit_percentage"] = result_data.get("technical_skill_fit_percentage", 65.0)
            result_data["non_technical_skill_fit_percentage"] = result_data.get("non_technical_skill_fit_percentage", 60.0)

        submission_json = json.dumps(submission_data)
        result_json = json.dumps(result_data)

        connection = get_db_connection()
        cursor = connection.cursor()

        # ✅ 1. Save to user_results (for archive)
        cursor.execute("""
            INSERT INTO user_results (user_id, submission_data, result_data)
            VALUES (%s, %s, %s)
        """, (user_id, submission_json, result_json))

        # ✅ 2. Try to update latest incomplete trial
        cursor.execute("""
            UPDATE user_trials
            SET 
                status_class = %s,
                status_label = %s,
                result_data = %s,
                is_submitted = TRUE,
                last_updated = CURRENT_TIMESTAMP
            WHERE user_id = %s AND is_submitted = FALSE
            ORDER BY created_at DESC
            LIMIT 1
        """, (
            'completed',
            'Completed',
            result_json,
            user_id
        ))

        # ✅ 3. If no row updated → insert new trial
        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT INTO user_trials (user_id, status_class, status_label, result_data, is_submitted)
                VALUES (%s, %s, %s, %s, TRUE)
            """, (
                user_id,
                'completed',
                'Completed',
                result_json
            ))

        connection.commit()

        return jsonify({
            "success": True,
            "message": "✅ Result saved successfully and trial recorded"
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

# ✅ 4. Fetch User Results
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

# ✅ 5. Get User Profile (guest & real)
@user_routes.route('/profile/<user_id>', methods=['GET'])
def get_user_profile(user_id):
    connection = None
    try:
        if user_id.startswith("guest_"):
            return jsonify({
                "success": True,
                "user": {
                    "id": user_id,
                    "full_name": "Guest User",
                    "email": None,
                    "registration_date": None,
                    "role": "guest",
                    "avatar": None
                },
                "guest": True,
                "latest_trial": None
            }), 200

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ 1. Fetch user info
        cursor.execute("""
            SELECT google_user_id AS id, full_name, email, registration_date, role, avatar
            FROM users
            WHERE google_user_id = %s
        """, (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        # ✅ 2. Fetch latest submitted trial
        cursor.execute("""
            SELECT saved_data, result_data, last_updated
            FROM user_trials
            WHERE user_id = %s AND is_submitted = TRUE
            ORDER BY last_updated DESC
            LIMIT 1
        """, (user_id,))
        trial = cursor.fetchone()

        # ✅ 3. Return full profile
        return jsonify({
            "success": True,
            "user": user,
            "guest": False,
            "latest_trial": {
                "saved_data": json.loads(trial["saved_data"]) if trial and trial["saved_data"] else None,
                "result_data": json.loads(trial["result_data"]) if trial and trial["result_data"] else None,
                "last_updated": trial["last_updated"].isoformat() if trial and trial["last_updated"] else None
            } if trial else None
        }), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error fetching profile: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection and connection.is_connected():
            connection.close()

# ✅ 6. Delete User Result
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

# ✅ 7. Logout (Optional)
@user_routes.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out."}), 200

# ✅ 8. Save Trial Progress or Completion
@user_routes.route('/wizard/save-trial', methods=['POST'])
def save_user_trial():
    connection = None
    try:
        data = request.get_json()

        user_id = data.get("user_id")
        status_class = data.get("status_class")
        status_label = data.get("status_label")
        saved_data = data.get("saved_data")
        result_data = data.get("result_data")
        is_submitted = data.get("is_submitted", False)

        if not user_id or not status_class or not status_label:
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO user_trials (
                user_id, status_class, status_label,
                saved_data, result_data, is_submitted, last_updated
            )
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (
            user_id,
            status_class,
            status_label,
            json.dumps(saved_data) if saved_data else None,
            json.dumps(result_data) if result_data else None,
            is_submitted
        ))

        connection.commit()

        return jsonify({"success": True, "message": "Trial saved"}), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error saving trial: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection and connection.is_connected():
            connection.close()

# ✅ 9. Get All Trials for User (Profile Timeline)
@user_routes.route('/profile/trials/<user_id>', methods=['GET'])
def get_user_trials(user_id):
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, status_class, status_label, is_submitted, created_at, last_updated
            FROM user_trials
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))

        trials = cursor.fetchall()

        return jsonify({"success": True, "trials": trials}), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error fetching trials: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection and connection.is_connected():
            connection.close()
# ✅ New: Fetch one trial by ID (for resume or summary)
@user_routes.route('/trial/<int:trial_id>', methods=['GET'])
def get_trial_result_by_id(trial_id):
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT result_data
            FROM user_trials
            WHERE id = %s AND is_submitted = TRUE
        """, (trial_id,))
        row = cursor.fetchone()

        if not row or not row["result_data"]:
            return jsonify({"success": False, "message": "No submitted result found"}), 404

        result_data = json.loads(row["result_data"])

        # ✅ Convert flat structure to full nested structure if needed
        if "recommended_positions" not in result_data:
            patched_position = {
                "position_name": result_data.get("recommended_position", "Unknown"),
                "fit_level": result_data.get("fit_level", "Unknown"),
                "match_score_percentage": result_data.get("match_score_percentage", 0),
                "subject_fit_percentage": result_data.get("subject_fit_percentage", 75.0),
                "technical_skill_fit_percentage": result_data.get("technical_skill_fit_percentage", 65.0),
                "non_technical_skill_fit_percentage": result_data.get("non_technical_skill_fit_percentage", 60.0),
                "position_id": result_data.get("position_id", 1)
            }

            result_data = {
                "recommended_positions": [patched_position],
                "companies": result_data.get("companies", []),
                "should_fetch_companies": True
            }

        # ✅ Otherwise, make sure percentages exist inside each recommended position
        for pos in result_data.get("recommended_positions", []):
            pos["subject_fit_percentage"] = pos.get("subject_fit_percentage", 75.0)
            pos["technical_skill_fit_percentage"] = pos.get("technical_skill_fit_percentage", 65.0)
            pos["non_technical_skill_fit_percentage"] = pos.get("non_technical_skill_fit_percentage", 60.0)

        return jsonify({
            "success": True,
            "trialData": {
                "result_data": result_data
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error loading trial result: {e}")
        return jsonify({"success": False, "message": "Server error"}), 500

    finally:
        if connection and connection.is_connected():
            connection.close()
