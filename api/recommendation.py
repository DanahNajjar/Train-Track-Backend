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

# ✅ Fit level logic (based on percentage of min_fit_score)
def get_fit_level(overall_percentage):
    if overall_percentage >= 125:
        return "Perfect Match"
    elif overall_percentage >= 100:
        return "Very Strong Match"
    elif overall_percentage >= 87.5:
        return "Strong Match"
    elif overall_percentage >= 75:
        return "Partial Match"
    else:
        return "No Match"

@recommendation_routes.route('/recommendations', methods=['POST'])
def get_recommendations():
    current_app.logger.info("\U0001F680 Starting recommendation analysis...")
    data = request.get_json()

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Extract input
        subject_ids = set(data.get("subjects", []))
        tech_skills = set(data.get("technical_skills", []))
        non_tech_skills = set(data.get("non_technical_skills", []))

        # ✅ Validate
        validation_error = validate_user_input(subject_ids, tech_skills, non_tech_skills)
        if validation_error:
            return jsonify({"success": False, "message": validation_error}), 400

        # ✅ Get types of prerequisites
        cursor.execute("SELECT id, type FROM prerequisites")
        prerequisite_info = {int(row['id']): row['type'] for row in cursor.fetchall()}

        # ✅ Get all position prerequisites
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
                    "min_fit_score": row["min_fit_score"] or 1,
                    "subjects": [],
                    "technical_skills": [],
                    "non_technical_skills": []
                }

            key = type_.lower().replace('-', '_') + 's'
            positions[pos_id][key].append((preq_id, weight))

        # ✅ Compute match per position
        results = []
        for pos_id, pos in positions.items():
            total_subject_weight = sum(w for _, w in pos["subjects"])
            total_tech_weight = sum(w for _, w in pos["technical_skills"])
            total_nontech_weight = sum(w for _, w in pos["non_technical_skills"])

            matched_subject = sum(w for pid, w in pos["subjects"] if pid in subject_ids)
            matched_tech = sum(w for pid, w in pos["technical_skills"] if pid in tech_skills)
            matched_nontech = sum(w for pid, w in pos["non_technical_skills"] if pid in non_tech_skills)

            matched_weight = matched_subject + matched_tech + matched_nontech
            min_fit_score = pos["min_fit_score"]

            overall_percentage = round((matched_weight / min_fit_score) * 100, 2)
            fit_level = get_fit_level(overall_percentage)

            if fit_level != "No Match":
                results.append({
                    "position_id": pos_id,
                    "position_name": pos["position_name"],
                    "match_score": matched_weight,
                    "match_score_percentage": overall_percentage,
                    "fit_level": fit_level,
                    "overall_fit_percentage": overall_percentage,
                    "subject_fit_percentage": round((matched_subject / total_subject_weight) * 100, 2) if total_subject_weight else 0,
                    "technical_skill_fit_percentage": round((matched_tech / total_tech_weight) * 100, 2) if total_tech_weight else 0,
                    "non_technical_skill_fit_percentage": round((matched_nontech / total_nontech_weight) * 100, 2) if total_nontech_weight else 0
                })

        results.sort(key=lambda x: x["match_score"], reverse=True)

        return jsonify({
            "success": True,
            "fallback_possible": False,
            "fallback_triggered": len(results) == 0,
            "recommended_positions": results
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection.is_connected():
            connection.close()
