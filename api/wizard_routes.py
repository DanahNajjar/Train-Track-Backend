from flask import Blueprint, request, jsonify
import mysql.connector
import base64

wizard_routes = Blueprint('wizard_routes', __name__)

# ✅ Upload category images once
def upload_category_images_once():
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Traintrack@2025",
        database="expert_system"
    )

# ✅ Call once when app starts
upload_category_images_once()

# ✅ DB connection for endpoints
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Traintrack@2025",
        database="expert_system"
    )

# ✅ Step 1: Get Majors
@wizard_routes.route('/wizard/majors', methods=['GET'])
def get_majors():
    majors = [
        { "id": 1, "name": "Computer Science Apprenticeship Program" },
        { "id": 2, "name": "Management Information Systems" },
        { "id": 163, "name": "Computer Science" },
        { "id": 164, "name": "Cyber Security" },
        { "id": 165, "name": "Computer Engineering" }
    ]
    return jsonify({ "success": True, "data": majors }), 200

# ✅ Step 2: Get Subject Categories (IDs 11–18 Only, With Description & Image)
@wizard_routes.route('/wizard/subject-categories', methods=['GET'])
def get_subject_categories():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, description, image_path AS image_url
        FROM categories
        WHERE id BETWEEN 11 AND 18
    """)
    categories = cursor.fetchall()
    connection.close()
    return jsonify({ "success": True, "data": categories }), 200


# ✅ Step 2.1: Get Subjects by Category IDs (With Category Name)
@wizard_routes.route('/wizard/subjects', methods=['GET'])
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
@wizard_routes.route('/wizard/technical-skills', methods=['GET'])
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
        SELECT DISTINCT p.id, p.name, csm.category_id, c.name AS category_name
        FROM prerequisites p
        JOIN category_skill_map csm ON p.id = csm.skill_id
        JOIN categories c ON csm.category_id = c.id
        WHERE p.type = 'Technical Skill' AND csm.category_id IN ({format_strings})
    """
    cursor.execute(query, category_ids)
    rows = cursor.fetchall()
    connection.close()

    grouped = {}
    for row in rows:
        cid = row['category_id']
        if cid not in grouped:
            grouped[cid] = {
                "Subject_category_id": cid,
                "Subject_category_name": row['category_name'],
                "skills": []
            }
        grouped[cid]['skills'].append({"id": row['id'], "name": row['name']})

    return jsonify({ "success": True, "data": list(grouped.values()) }), 200

# ✅ Step 4: Get Non-Technical Skills (Simple List)
@wizard_routes.route('/wizard/non-technical-skills', methods=['GET'])
def get_non_technical_skills():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, name
        FROM prerequisites
        WHERE type = 'Non-Technical Skill'
    """)
    skills = cursor.fetchall()
    connection.close()

    return jsonify({ "success": True, "data": skills }), 200

# ✅ Step 5: Save Advanced Preferences
@wizard_routes.route('/wizard/preferences', methods=['POST'])
def save_advanced_preferences():
    data = request.get_json()

    # Extract inputs
    training_mode = data.get('training_mode')
    company_size = data.get('preferred_company_size')
    culture = data.get('preferred_culture')
    industry = data.get('preferred_industry')

    # ❗ Check if any required field is missing
    if training_mode is None or company_size is None or culture is None or industry is None:
        return jsonify({
            "success": False,
            "message": "All fields (training_mode, preferred_company_size, preferred_culture, preferred_industry) are required."
        }), 400

    # ✅ Optional: Validate values if present
    if training_mode not in ['Onsite', 'Remote', 'Hybrid']:
        return jsonify({ "success": False, "message": "Invalid training mode." }), 400

    if company_size not in ['Small', 'Medium', 'Large']:
        return jsonify({ "success": False, "message": "Invalid company size." }), 400

    if not isinstance(culture, list) or len(culture) > 2:
        return jsonify({ "success": False, "message": "Culture must be a list with up to 2 values." }), 400

    if not isinstance(industry, list) or len(industry) > 2:
        return jsonify({ "success": False, "message": "Industry must be a list with up to 2 values." }), 400

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
@wizard_routes.route('/wizard/summary', methods=['POST'])
def wizard_summary():
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

    # ✅ Fetch major name
    cursor.execute("SELECT name FROM prerequisites WHERE id = %s AND type = 'Major'", (major_id,))
    major_row = cursor.fetchone()
    major_name = major_row['name'] if major_row else None

    # ✅ Fetch subjects grouped by category
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
            grouped_subjects[cat_id]["subjects"].append({
                "id": row["id"],
                "name": row["name"]
            })

        subject_names_by_cat = list(grouped_subjects.values())

    # ✅ Fetch technical skills grouped by subject category
    tech_skills_by_cat = []
    if technical_skill_ids:
        format_strings = ','.join(['%s'] * len(technical_skill_ids))
        query = f"""
            SELECT p.id, p.name, c.id AS category_id, c.name AS category_name
            FROM prerequisites p
            JOIN category_skill_map m ON p.id = m.skill_id
            JOIN categories c ON m.category_id = c.id
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
            # Avoid duplicate skills
            if not any(s["id"] == row["id"] for s in grouped_skills[cat_id]["skills"]):
                grouped_skills[cat_id]["skills"].append({
                    "id": row["id"],
                    "name": row["name"]
                })

        tech_skills_by_cat = list(grouped_skills.values())

    # ✅ Fetch non-technical skills
    non_tech_names = []
    if non_technical_skill_ids:
        format_strings = ','.join(['%s'] * len(non_technical_skill_ids))
        query = f"""
            SELECT name FROM prerequisites
            WHERE id IN ({format_strings}) AND type = 'Non-Technical Skill'
        """
        cursor.execute(query, tuple(non_technical_skill_ids))
        non_tech_names = [row['name'] for row in cursor.fetchall()]

    connection.close()

    return jsonify({
        "success": True,
        "summary": {
            "full_name": full_name,
            "gender": gender,
            "major": major_name,
            "subjects": subject_names_by_cat,
            "technical_skills": tech_skills_by_cat,
            "non_technical_skills": non_tech_names,
            "preferences": preferences or {}
        }
    }), 200


