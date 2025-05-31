from flask import Blueprint, request, jsonify, current_app
from api.db import get_db_connection
import base64
import os
import logging
from collections import OrderedDict
import json

# Setup Logging
logging.basicConfig(level=logging.INFO)

wizard_routes = Blueprint('wizard_routes', __name__)
# Log error messages
def log_error(error_message):
    logging.error(f"Error occurred: {error_message}")

# ✅ Upload category images once
def upload_category_images_once():
    connection = get_db_connection()
    connection.close()

# ✅ Call once when app starts
try:
    upload_category_images_once()
except Exception as e:
    log_error(f"❌ Failed to upload category images at startup: {e}")


# ✅ Helper function to build 'IN' clause dynamically
def build_in_clause(ids):
    return ','.join(['%s'] * len(ids)), tuple(ids)

# ✅ Generalized response function
def create_response(success, data=None, message=None, status_code=200):
    return jsonify({
        "success": success,
        "data": data,
        "message": message
    }), status_code
@wizard_routes.route('/debug-db')
def debug_db():
    return jsonify({
        "environment": os.getenv("FLASK_ENV"),
        "db_host": os.getenv("DB_HOST"),
        "db_name": os.getenv("DB_NAME")
    })

# ✅ Step 1: Get Majors
@wizard_routes.route('/majors', methods=['GET'])
def get_majors():
    majors = [
        {"id": 1, "name": "Computer Science Apprenticeship Program"},
        {"id": 2, "name": "Management Information Systems"},
        {"id": 163, "name": "Computer Science"},
        {"id": 164, "name": "Cyber Security"},
        {"id": 165, "name": "Computer Engineering"}
    ]
    return create_response(True, majors)

# ✅ Step 2: Get Subject Categories
@wizard_routes.route('/subject-categories', methods=['GET'])
def get_subject_categories():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, name, description
            FROM categories
            WHERE id BETWEEN 11 AND 18
        """)
        rows = cursor.fetchall()

        base_url = request.host_url.rstrip('/')
        categories = []
        for row in rows:
            static_path = f"/static/categories/{row['id']}.png"
            full_url = f"{base_url}{static_path}"
            categories.append({
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "image_url": full_url
            })

        return create_response(True, categories)
    except Exception as e:
        log_error(f"Error fetching subject categories: {e}")
        return create_response(False, message=str(e), status_code=500)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# ✅ Step 3: Get Subjects by Category IDs (With Category Name)
@wizard_routes.route('/subjects', methods=['GET'])
def get_subjects_by_categories():
    ids_param = request.args.get('ids')
    if not ids_param:
        return create_response(False, message="Missing category ids.", status_code=400)

    try:
        category_ids = [int(x) for x in ids_param.split(',')]
    except ValueError:
        return create_response(False, message="Invalid category id format.", status_code=400)

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    format_strings, category_ids = build_in_clause(category_ids)
    query = f"""
        SELECT p.id, p.name, p.category_id, c.name AS category_name
        FROM prerequisites p
        JOIN categories c ON p.category_id = c.id
        WHERE p.type = 'Subject' AND p.category_id IN ({format_strings})
    """
    cursor.execute(query, category_ids)
    results = cursor.fetchall()
    connection.close()

    grouped = {}
    for row in results:
        cid = row['category_id']
        if cid not in grouped:
            grouped[cid] = {
                "Subject_category_id": cid,
                "Subject_category_name": row['category_name'],
                "subjects": []
            }
        grouped[cid]["subjects"].append({"id": row['id'], "name": row['name']})

    return create_response(True, list(grouped.values()))

# ✅ Step 4: Get Technical Skills by Category IDs
# ✅ Step 4: Get Technical Skills by Category IDs
@wizard_routes.route('/technical-skills', methods=['GET'])
def get_technical_skills_grouped():
    ids_param = request.args.get('category_ids')
    if not ids_param:
        return create_response(False, message="Missing category ids.", status_code=400)

    try:
        category_ids = [int(x) for x in ids_param.split(',')]
    except ValueError:
        return create_response(False, message="Invalid category id format.", status_code=400)

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    format_strings, category_ids = build_in_clause(category_ids)

    query = f"""
        SELECT 
            p.id,
            p.name,
            csm.category_id AS subject_category_id,
            sc.name AS subject_category_name,
            tc.name AS tech_category_name
        FROM prerequisites p
        JOIN category_skill_map csm ON p.id = csm.skill_id
        JOIN categories sc ON csm.category_id = sc.id           -- Subject category name
        JOIN categories tc ON p.category_id = tc.id             -- Technical category name
        WHERE p.type = 'Technical Skill' AND csm.category_id IN ({format_strings})
        ORDER BY sc.id, tc.name, p.name
    """
    cursor.execute(query, category_ids)
    rows = cursor.fetchall()
    connection.close()

    subject_grouped = {}
    globally_seen_skill_ids = set()  # ✅ Deduplication across all groups

    for row in rows:
        skill_id = row["id"]
        if skill_id in globally_seen_skill_ids:
            continue  # ✅ Skip if already shown globally
        globally_seen_skill_ids.add(skill_id)

        skill_name = row["name"]
        subject_id = row["subject_category_id"]
        subject_name = row["subject_category_name"]
        tech_cat = row["tech_category_name"].strip().title()

        if subject_id not in subject_grouped:
            subject_grouped[subject_id] = {
                "Subject_category_id": subject_id,
                "Subject_category_name": subject_name,
                "tech_categories": {}
            }

        tech_group = subject_grouped[subject_id]["tech_categories"]
        if tech_cat not in tech_group:
            tech_group[tech_cat] = []

        tech_group[tech_cat].append({
            "id": skill_id,
            "name": skill_name
        })

    # ✅ Convert nested dict to final list format
    final_output = []
    for subject in subject_grouped.values():
        formatted = []
        for cat_name, skills in subject["tech_categories"].items():
            if skills:  # ✅ only add categories with skills
                formatted.append({
                    "tech_category_name": cat_name,
                    "skills": skills
                })

        if formatted:  # ✅ only add subject group if it has at least one skill
            final_output.append({
                "Subject_category_id": subject["Subject_category_id"],
                "Subject_category_name": subject["Subject_category_name"],
                "tech_categories": formatted
            })

    return create_response(True, final_output)

    # ✅ Step 4: Get Non-Technical Skills
@wizard_routes.route('/non-technical-skills', methods=['GET'])
def get_non_technical_skills():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, name
            FROM prerequisites
            WHERE type = 'Non-Technical Skill'
            ORDER BY name
        """)
        skills = cursor.fetchall()

        return create_response(True, skills)

    except Exception as e:
        log_error(f"Error fetching non-technical skills: {e}")
        return create_response(False, message=str(e), status_code=500)
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            
# ✅ Step 5: Save Advanced Preferences 
@wizard_routes.route('/preferences', methods=['GET'])
def get_advanced_preferences():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Fetch training modes first
        cursor.execute("SELECT id, description FROM training_modes")
        training_modes = cursor.fetchall()

        # ✅ Fetch company sizes second
        cursor.execute("SELECT id, description FROM company_sizes")
        company_sizes = cursor.fetchall()

        # ✅ Fetch company cultures third
        cursor.execute("SELECT id, name FROM company_culture_keywords")
        company_cultures = cursor.fetchall()

        # ✅ Fetch industries fourth
        cursor.execute("SELECT id, name FROM industries")
        industries = cursor.fetchall()

        # ✅ Organize the JSON exactly in your requested order
        return jsonify({
            "success": True,
            "data": {
                "training_modes": training_modes,       # First
                "company_sizes": company_sizes,         # Second
                "company_cultures": company_cultures,   # Third
                "industries": industries                # Fourth
            }
        }), 200

    except Exception as e:
        log_error(f"Error fetching preferences: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
@wizard_routes.route('/submit', methods=['POST'])
def submit_wizard():
    connection = None
    try:
        data = request.get_json()

        # ✅ Required fields
        full_name = data.get('full_name')
        gender = data.get('gender')
        major_id = data.get('major_id')
        date_of_birth = data.get('date_of_birth')

        # ✅ Optional fields
        selected_subject_ids = data.get('selected_subject_ids', [])
        selected_technical_skill_ids = data.get('selected_technical_skill_ids', [])
        selected_non_technical_skill_ids = data.get('selected_non_technical_skills', [])
        advanced_preferences = data.get('advanced_preferences') or {}

        if not all([full_name, gender, major_id, date_of_birth]):
            return jsonify({"success": False, "message": "Missing basic user info."}), 400

        # ✅ Open DB connection
        connection = get_db_connection()
        cursor = connection.cursor()

        # ✅ Save basic info
        cursor.execute("""
            INSERT INTO wizard_submissions (full_name, gender, major_id, date_of_birth)
            VALUES (%s, %s, %s, %s)
        """, (full_name, gender, major_id, date_of_birth))
        submission_id = cursor.lastrowid

        # ✅ Save subjects
        for subject_id in selected_subject_ids:
            cursor.execute("""
                INSERT INTO wizard_submission_subjects (submission_id, subject_id)
                VALUES (%s, %s)
            """, (submission_id, subject_id))

        # ✅ Save technical skills
        for skill_id in selected_technical_skill_ids:
            cursor.execute("""
                INSERT INTO wizard_submission_technical_skills (submission_id, skill_id)
                VALUES (%s, %s)
            """, (submission_id, skill_id))

        # ✅ Save non-technical skills
        for nontech_id in selected_non_technical_skill_ids:
            cursor.execute("""
                INSERT INTO wizard_submission_nontechnical_skills (submission_id, nontech_skill_id)
                VALUES (%s, %s)
            """, (submission_id, nontech_id))

        # ✅ Save advanced preferences using correct column names
        training_mode_id = (advanced_preferences.get('training_modes') or [None])[0]
        company_size_id = (advanced_preferences.get('company_sizes') or [None])[0]
        company_culture_ids = (
            ','.join(map(str, advanced_preferences.get('company_culture', [])))
            if advanced_preferences.get('company_culture') else None
        )
        preferred_industry_ids = (
            ','.join(map(str, advanced_preferences.get('industries', [])))
            if advanced_preferences.get('industries') else None
        )

        cursor.execute("""
            INSERT INTO wizard_submission_advanced_preferences (
                submission_id, training_mode_id, company_size_id, company_culture_ids, preferred_industry_ids
            ) VALUES (%s, %s, %s, %s, %s)
        """, (submission_id, training_mode_id, company_size_id, company_culture_ids, preferred_industry_ids))

        # ✅ Commit changes
        connection.commit()
        return jsonify({"success": True, "message": "Wizard data submitted!"}), 201

    except Exception as e:
        current_app.logger.error(f"🔥 Error in /submit: {str(e)}")
        return jsonify({"success": False, "message": "Internal server error."}), 500

    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
