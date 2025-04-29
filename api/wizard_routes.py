from flask import Blueprint, request, jsonify
import mysql.connector
import base64
import os
import logging
from collections import OrderedDict

# Setup Logging
logging.basicConfig(level=logging.INFO)

wizard_routes = Blueprint('wizard_routes', __name__)

# ✅ DB connection for all use cases
def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.environ.get("DB_HOST"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            database=os.environ.get("DB_NAME"),
            port=int(os.environ.get("DB_PORT", 3306))
        )
    except mysql.connector.Error as err:
        log_error(f"Database connection failed: {err}")
        raise

# Log error messages
def log_error(error_message):
    logging.error(f"Error occurred: {error_message}")

# ✅ Upload category images once
def upload_category_images_once():
    connection = get_db_connection()
    connection.close()

# ✅ Call once when app starts
upload_category_images_once()

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
        JOIN categories sc ON csm.category_id = sc.id
        JOIN categories tc ON p.category_id = tc.id
        WHERE p.type = 'Technical Skill' AND csm.category_id IN ({format_strings})
        ORDER BY sc.id, tc.name, p.name
    """
    cursor.execute(query, category_ids)
    rows = cursor.fetchall()
    connection.close()

    subject_grouped = {}
    for row in rows:
        sub_id = row['subject_category_id']
        sub_name = row['subject_category_name']
        tech_cat = row['tech_category_name']

        if sub_id not in subject_grouped:
            subject_grouped[sub_id] = {
                "Subject_category_id": sub_id,
                "Subject_category_name": sub_name,
                "tech_categories": {}
            }

        tech_group = subject_grouped[sub_id]["tech_categories"]
        if tech_cat not in tech_group:
            tech_group[tech_cat] = []

        tech_group[tech_cat].append({
            "id": row["id"],
            "name": row["name"]
        })

    final_output = []
    for subject_data in subject_grouped.values():
        tech_cats_list = []
        for cat_name, skills in subject_data["tech_categories"].items():
            tech_cats_list.append({
                "tech_category_name": cat_name,
                "skills": skills
            })

        final_output.append({
            "Subject_category_id": subject_data["Subject_category_id"],
            "Subject_category_name": subject_data["Subject_category_name"],
            "tech_categories": tech_cats_list
        })

    return create_response(True, final_output)

# ✅ Step 5: Save Advanced Preferences 
@wizard_routes.route('/preferences', methods=['GET'])
def get_advanced_preferences():
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Query to fetch human-readable terms by joining the lookup tables
        cursor.execute("""
            SELECT tm.mode AS training_mode, cs.size AS company_size, c.culture_name AS culture, i.industry_name AS industry
            FROM default_preferences dp
            JOIN training_modes tm ON dp.training_mode_id = tm.id
            JOIN company_sizes cs ON dp.company_size_id = cs.id
            JOIN cultures c ON dp.culture_id = c.id
            JOIN industries i ON dp.industry_id = i.id
        """)
        preferences = cursor.fetchone()

        if not preferences:
            return jsonify({"success": False, "message": "No preferences found."}), 204  # No content found

        # Parse culture and industry if they exist (assuming comma-separated lists)
        culture_list = preferences['culture'].split(',') if preferences.get('culture') else []
        industry_list = preferences['industry'].split(',') if preferences.get('industry') else []

        return jsonify({
            "success": True,
            "data": {
                "training_mode": preferences['training_mode'],
                "company_size": preferences['company_size'],
                "preferred_culture": culture_list,
                "preferred_industry": industry_list
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500  # Internal Server Error

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            
# ✅ Full Submit Wizard Endpoint
@wizard_routes.route('/submit', methods=['POST'])
def submit_wizard():
    try:
        # Step 1: Get all user data from the frontend
        data = request.get_json()

        full_name = data.get('full_name')
        gender = data.get('gender')
        major_id = data.get('major_id')
        selected_subject_ids = data.get('selected_subject_ids', [])
        selected_technical_skill_ids = data.get('selected_technical_skill_ids', [])
        selected_non_technical_skill_ids = data.get('selected_non_technical_skill_ids', [])
        advanced_preferences = data.get('advanced_preferences')  # object or null

        # Step 2: Basic Validation
        if not (full_name and gender and major_id):
            return jsonify({"success": False, "message": "Missing basic user information."}), 400

        # Step 3: Save to database
        connection = get_db_connection()
        cursor = connection.cursor()

        # 3.1 Insert basic user info into wizard_submissions
        cursor.execute("""
            INSERT INTO wizard_submissions (full_name, gender, major_id)
            VALUES (%s, %s, %s)
        """, (full_name, gender, major_id))

        # Get the new submission ID
        submission_id = cursor.lastrowid

        # 3.2 Insert selected subject topics (not subject categories)
        for subject_id in selected_subject_ids:
            cursor.execute("""
                INSERT INTO wizard_submission_subjects (submission_id, subject_id)
                VALUES (%s, %s)
            """, (submission_id, subject_id))

        # 3.3 Insert selected technical skills
        for tech_skill_id in selected_technical_skill_ids:
            cursor.execute("""
                INSERT INTO wizard_submission_technical_skills (submission_id, skill_id)
                VALUES (%s, %s)
            """, (submission_id, tech_skill_id))

        # 3.4 Insert selected non-technical skills
        for nontech_skill_id in selected_non_technical_skill_ids:
            cursor.execute("""
                INSERT INTO wizard_submission_nontechnical_skills (submission_id, nontech_skill_id)
                VALUES (%s, %s)
            """, (submission_id, nontech_skill_id))

        # 3.5 Insert advanced preferences only if they exist
        if advanced_preferences:
            training_mode = advanced_preferences.get('training_mode')
            company_size = advanced_preferences.get('company_size')
            company_culture = ','.join(advanced_preferences.get('company_culture', [])) if advanced_preferences.get('company_culture') else None
            preferred_industry = ','.join(advanced_preferences.get('preferred_industry', [])) if advanced_preferences.get('preferred_industry') else None

            cursor.execute("""
                INSERT INTO wizard_submission_advanced_preferences (submission_id, training_mode, company_size, company_culture, preferred_industry)
                VALUES (%s, %s, %s, %s, %s)
            """, (submission_id, training_mode, company_size, company_culture, preferred_industry))

        # Step 4: Finalize
        connection.commit()

        return jsonify({"success": True, "message": "Wizard data submitted successfully!"}), 201

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# ✅ Step 6: Return Wizard Summary
@wizard_routes.route('/user-input-summary', methods=['POST'])
def user_input_summary():
    try:
        data = request.get_json()
        full_name = data.get("full_name")
        gender = data.get("gender")
        major_id = data.get("major_id")
        subject_ids = data.get("subjects", [])
        technical_skill_ids = data.get("technical_skills", [])
        non_technical_skill_ids = data.get("non_technical_skills", [])
        preferences = data.get("preferences", {})

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Get Major Name
        cursor.execute("SELECT name FROM prerequisites WHERE id = %s AND type = 'Major'", (major_id,))
        major_row = cursor.fetchone()
        major_name = major_row['name'] if major_row else None

        # ✅ Get Selected Subjects
        subject_names_by_cat = []
        if subject_ids:
            format_strings, category_ids = build_in_clause(subject_ids)
            query = f"""
                SELECT p.id, p.name, c.id AS category_id, c.name AS category_name
                FROM prerequisites p
                JOIN categories c ON p.category_id = c.id
                WHERE p.id IN ({format_strings}) AND p.type = 'Subject'
            """
            cursor.execute(query, tuple(subject_ids))
            rows = cursor.fetchall()
            grouped_subjects = {}
            for row in rows:
                cat_id = row['category_id']
                if cat_id not in grouped_subjects:
                    grouped_subjects[cat_id] = {
                        "category_id": cat_id,
                        "category_name": row['category_name'],
                        "subjects": []
                    }
                grouped_subjects[cat_id]["subjects"].append({"id": row["id"], "name": row["name"]})
            subject_names_by_cat = list(grouped_subjects.values())

        # ✅ Get Technical Skills
        tech_skills_by_cat = []
        if technical_skill_ids:
            format_strings, category_ids = build_in_clause(technical_skill_ids)
            query = f"""
                SELECT p.id, p.name, c.id AS category_id, c.name AS category_name
                FROM prerequisites p
                JOIN categories c ON p.category_id = c.id
                WHERE p.id IN ({format_strings}) AND p.type = 'Technical Skill'
            """
            cursor.execute(query, tuple(technical_skill_ids))
            rows = cursor.fetchall()
            grouped_skills = {}
            for row in rows:
                cat_id = row['category_id']
                if cat_id not in grouped_skills:
                    grouped_skills[cat_id] = {
                        "category_id": cat_id,
                        "category_name": row["category_name"],
                        "skills": []
                    }
                grouped_skills[cat_id]["skills"].append({"id": row["id"], "name": row["name"]})
            tech_skills_by_cat = list(grouped_skills.values())

        # ✅ Get Non-Technical Skills
        non_tech_names = []
        if non_technical_skill_ids:
            format_strings, category_ids = build_in_clause(non_technical_skill_ids)
            query = f"""
                SELECT name FROM prerequisites
                WHERE id IN ({format_strings}) AND type = 'Non-Technical Skill'
            """
            cursor.execute(query, tuple(non_technical_skill_ids))
            non_tech_names = [row['name'] for row in cursor.fetchall()]

        # ✅ Final Output: Ordered by Wizard Steps
        user_info = OrderedDict()
        user_info["full_name"] = full_name
        user_info["gender"] = gender
        user_info["major"] = major_name
        user_info["subjects"] = subject_names_by_cat
        user_info["technical_skills"] = tech_skills_by_cat
        user_info["non_technical_skills"] = non_tech_names
        user_info["preferences"] = preferences

        return create_response(True, user_info)

    except Exception as e:
        log_error(f"Error in user input summary: {e}")
        return create_response(False, message=str(e), status_code=500)
    finally:
        if connection.is_connected():
            connection.close()
