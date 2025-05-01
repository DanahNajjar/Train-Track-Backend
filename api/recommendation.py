from flask import Blueprint, request, jsonify, current_app
from api.db import get_db_connection

recommendation_routes = Blueprint('recommendation', __name__)

# ✅ Input validation
def validate_user_input(subject_ids, tech_skills, non_tech_skills):
    if not 3 <= len(subject_ids) <= 7:
        return "Please select between 3 and 7 subjects."
    if not 3 <= len(tech_skills) <= 8:
        return "Please select between 3 and 8 technical skills."
    if not 3 <= len(non_tech_skills) <= 5:
        return "Please select between 3 and 5 non-technical skills."
    return None

# ✅ Fit level tiers
def get_fit_level(overall_percentage):
    if overall_percentage >= 87.5:
        return "Perfect Match"
    elif overall_percentage >= 75:
        return "Very Strong Match"
    elif overall_percentage >= 62.5:
        return "Strong Match"
    elif overall_percentage >= 50:
        return "Partial Match"
    else:
        return "No Match"

# ✅ Recommendation endpoint
@recommendation_routes.route('/recommendations', methods=['POST'])
def get_recommendations():
    current_app.logger.info("🚀 Starting recommendation analysis...")
    data = request.get_json()

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Extract + parse inputs
        subject_ids = set(map(int, data.get("subjects", [])))
        tech_skills = set(map(int, data.get("technical_skills", [])))
        non_tech_skills = set(map(int, data.get("non_technical_skills", [])))

        # ✅ Validate
        validation_error = validate_user_input(subject_ids, tech_skills, non_tech_skills)
        if validation_error:
            return jsonify({"success": False, "message": validation_error}), 400

        # ✅ Get prerequisite types
        cursor.execute("SELECT id, type FROM prerequisites")
        prerequisite_info = {int(row['id']): row['type'] for row in cursor.fetchall()}

        # ✅ Get all position prerequisites with weights
        cursor.execute("""
            SELECT pp.position_id, pp.prerequisite_id, pp.weight,
                   p.name AS position_name, p.min_fit_score
            FROM position_prerequisites pp
            JOIN positions p ON pp.position_id = p.id
        """)
        all_prereqs = cursor.fetchall()

        # ✅ Group prerequisites per position
        positions = {}
        for row in all_prereqs:
            pos_id = row['position_id']
            preq_id = int(row['prerequisite_id'])
            weight = row['weight']
            type_ = prerequisite_info.get(preq_id)

            if not type_ or type_ == "Major":
                continue

            if pos_id not in positions:
                positions[pos_id] = {
                    "position_name": row["position_name"],
                    "subjects": [],
                    "technical_skills": [],
                    "non_technical_skills": []
                }

            key_map = {
                "Subject": "subjects",
                "Technical Skill": "technical_skills",
                "Non-Technical Skill": "non_technical_skills"
            }

            if type_ in key_map:
                positions[pos_id][key_map[type_]].append((preq_id, weight))

        # ✅ Compute fit score per position
        results = []
        for pos_id, pos in positions.items():
            total_subject_weight = sum(w for _, w in pos["subjects"])
            total_tech_weight = sum(w for _, w in pos["technical_skills"])
            total_nontech_weight = sum(w for _, w in pos["non_technical_skills"])

            matched_subject = sum(w for pid, w in pos["subjects"] if pid in subject_ids)
            matched_tech = sum(w for pid, w in pos["technical_skills"] if pid in tech_skills)
            matched_nontech = sum(w for pid, w in pos["non_technical_skills"] if pid in non_tech_skills)

            # Skip positions with no prerequisites
            if total_subject_weight + total_tech_weight + total_nontech_weight == 0:
                continue

            # ✅ Normalize each component
            subject_percent = round((matched_subject / total_subject_weight) * 100, 2) if total_subject_weight else 0
            tech_percent = round((matched_tech / total_tech_weight) * 100, 2) if total_tech_weight else 0
            nontech_percent = round((matched_nontech / total_nontech_weight) * 100, 2) if total_nontech_weight else 0

            # ✅ Final normalized score (out of 100)
            overall_percentage = round((subject_percent + tech_percent + nontech_percent) / 3, 2)
            fit_level = get_fit_level(overall_percentage)

            if fit_level != "No Match":
                results.append({
                    "position_id": pos_id,
                    "position_name": pos["position_name"],
                    "fit_level": fit_level,
                    "normalized_fit_percentage": overall_percentage,
                    "subject_fit_percentage": subject_percent,
                    "technical_skill_fit_percentage": tech_percent,
                    "non_technical_skill_fit_percentage": nontech_percent
                })

        # ✅ Sort by normalized percentage
        results.sort(key=lambda x: x["normalized_fit_percentage"], reverse=True)

        return jsonify({
            "success": True,
            "fallback_possible": False,
            "fallback_triggered": len(results) == 0,
            "recommended_positions": results
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.error(f"❌ Error in recommendations: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection.is_connected():
            connection.close()
