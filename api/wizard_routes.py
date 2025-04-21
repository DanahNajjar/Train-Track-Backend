from flask import Blueprint, request, jsonify
import mysql.connector
import base64
import os
from collections import OrderedDict


wizard_routes = Blueprint('wizard_routes', __name__)

# ✅ DB connection for all use cases
def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        port=int(os.environ.get("DB_PORT", 3306))
    )


# ✅ Upload category images once
def upload_category_images_once():
    connection = get_db_connection()
    connection.close()

# ✅ Call once when app starts
upload_category_images_once()

# ✅ Step 1: Get Majors
@wizard_routes.route('/majors', methods=['GET'])
def get_majors():
    majors = [
        { "id": 1, "name": "Computer Science Apprenticeship Program" },
        { "id": 2, "name": "Management Information Systems" },
        { "id": 163, "name": "Computer Science" },
        { "id": 164, "name": "Cyber Security" },
        { "id": 165, "name": "Computer Engineering" }
    ]
    return jsonify({ "success": True, "data": majors }), 200


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

        # ✅ Detect your live backend base URL
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

        return jsonify({ "success": True, "data": categories }), 200

    except Exception as e:
        return jsonify({ "success": False, "error": str(e) }), 500

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# ✅ Step 2.1: Get Subjects by Category IDs (With Category Name)
@wizard_routes.route('/subjects', methods=['GET'])
def get_subjects_by_categories():
    ids_param = request.args.get('ids')
    if not ids_param:
        return jsonify({ "success": False, "message": "Missing category ids." }), 400

    try:
        category_ids = [int(x) for x in ids_param.split(',')]
    except ValueError:
        return jsonify({ "success": False, "message": "Invalid category id format." }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    format_strings = ','.join(['%s'] * len(category_ids))
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

    return jsonify({
        "success": True,
        "data": list(grouped.values())
    }), 200


# ✅ Step 3: Technical Skills by Subject Category IDs (Grouped, using category_id)
@wizard_routes.route('/technical-skills', methods=['GET'])
def get_technical_skills_grouped():
    ids_param = request.args.get('category_ids')
    if not ids_param:
        return jsonify({ "success": False, "message": "Missing category ids." }), 400

    try:
        category_ids = [int(x) for x in ids_param.split(',')]
    except ValueError:
        return jsonify({ "success": False, "message": "Invalid category id format." }), 400

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    format_strings = ','.join(['%s'] * len(category_ids))

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

    # ✅ Grouping by subject category → tech category → skills
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

    # ✅ Convert to required JSON format
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

    return jsonify({ "success": True, "data": final_output }), 200

    
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
        """)
        skills = cursor.fetchall()
        return jsonify({"success": True, "data": skills}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection.is_connected():
            connection.close()

# ✅ Step 5: Save Advanced Preferences
@wizard_routes.route('/preferences', methods=['POST'])
def save_advanced_preferences():
    try:
        data = request.get_json()
        training_mode = data.get('training_mode')
        company_size = data.get('preferred_company_size')
        culture = data.get('preferred_culture')
        industry = data.get('preferred_industry')

        if training_mode is None or company_size is None or culture is None or industry is None:
            return jsonify({"success": False, "message": "All fields are required."}), 400

        if training_mode not in ['Onsite', 'Remote', 'Hybrid']:
            return jsonify({"success": False, "message": "Invalid training mode."}), 400

        if company_size not in ['Small', 'Medium', 'Large']:
            return jsonify({"success": False, "message": "Invalid company size."}), 400

        if not isinstance(culture, list) or len(culture) > 2:
            return jsonify({"success": False, "message": "Culture must be a list with up to 2 values."}), 400

        if not isinstance(industry, list) or len(industry) > 2:
            return jsonify({"success": False, "message": "Industry must be a list with up to 2 values."}), 400

        return jsonify({
            "success": True,
            "message": "Preferences saved.",
            "data": {
                "training_mode": training_mode,
                "preferred_company_size": company_size,
                "preferred_culture": culture,
                "preferred_industry": industry
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ✅ Step 6: Return Wizard Summary (Organized by Wizard Flow)
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

        # ✅ Step 2: Get Selected Subjects (Grouped by Category)
        subject_names_by_cat = []
        if subject_ids:
            format_strings = ','.join(['%s'] * len(subject_ids))
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

        # ✅ Step 3: Get Technical Skills (Grouped by their actual technical skill categories 1–10)
        tech_skills_by_cat = []
        if technical_skill_ids:
            format_strings = ','.join(['%s'] * len(technical_skill_ids))
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
                if not any(s["id"] == row["id"] for s in grouped_skills[cat_id]["skills"]):
                    grouped_skills[cat_id]["skills"].append({"id": row["id"], "name": row["name"]})
            tech_skills_by_cat = list(grouped_skills.values())

        # ✅ Step 4: Get Non-Technical Skills
        non_tech_names = []
        if non_technical_skill_ids:
            format_strings = ','.join(['%s'] * len(non_technical_skill_ids))
            query = f"""
                SELECT name FROM prerequisites
                WHERE id IN ({format_strings}) AND type = 'Non-Technical Skill'
            """
            cursor.execute(query, tuple(non_technical_skill_ids))
            non_tech_names = [row['name'] for row in cursor.fetchall()]

        # ✅ Step 5: Preferences (Advanced, if provided)
        final_preferences = preferences if preferences else {}

        # ✅ Final Output: Ordered by Wizard Steps
        user_info = OrderedDict()
        user_info["full_name"] = full_name
        user_info["gender"] = gender
        user_info["major"] = major_name
        user_info["subjects"] = subject_names_by_cat
        user_info["technical_skills"] = tech_skills_by_cat
        user_info["non_technical_skills"] = non_tech_names
        user_info["preferences"] = final_preferences

        return jsonify({
            "success": True,
            "user_info": user_info
        }), 200

    except Exception as e:
        return jsonify({ "success": False, "message": str(e) }), 500

    finally:
        if connection.is_connected():
            connection.close()