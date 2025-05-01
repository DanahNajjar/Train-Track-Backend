from flask import Blueprint, request, jsonify, current_app
from api.db import get_db_connection

recommendation_routes = Blueprint('recommendation', __name__)

# Validation helper
def validate_user_input(subject_ids, tech_skills, non_tech_skills):
    if not 3 <= len(subject_ids) <= 7:
        return "Please select between 3 and 7 subjects."
    if not 3 <= len(tech_skills) <= 8:
        return "Please select between 3 and 8 technical skills."
    if not 3 <= len(non_tech_skills) <= 5:
        return "Please select between 3 and 5 non-technical skills."
    return None

# Fit Level helper
def get_fit_level(matched_score, min_fit_score):
    if matched_score >= min_fit_score * 1.25:
        return "Perfect Match"
    elif matched_score >= min_fit_score:
        return "Partial Match"
    else:
        return "No Match"

# Main Recommendation Endpoint
@recommendation_routes.route('/recommendations', methods=['POST'])
def get_recommendations():
    current_app.logger.info("🚀 Processing started for recommendations...")

    data = request.get_json()

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Extract Inputs
        subject_ids = set(data.get("subjects", []))
        tech_skills = set(data.get("technical_skills", []))
        non_tech_skills = set(data.get("non_technical_skills", []))

        current_app.logger.info(f"Subjects selected: {subject_ids}")
        current_app.logger.info(f"Technical Skills selected: {tech_skills}")
        current_app.logger.info(f"Non-Technical Skills selected: {non_tech_skills}")

        # ✅ Validate Inputs
        validation_error = validate_user_input(subject_ids, tech_skills, non_tech_skills)
        if validation_error:
            return jsonify({"success": False, "message": validation_error}), 400

        # ✅ Fetch prerequisite info
        cursor.execute("SELECT id, type FROM prerequisites")
        prerequisite_info = {int(row['id']): row['type'] for row in cursor.fetchall()}

        # ✅ Fetch position prerequisites
        cursor.execute("""
            SELECT 
                pp.position_id,
                pp.prerequisite_id,
                pp.weight,
                p.name AS position_name,
                p.min_fit_score
            FROM position_prerequisites pp
            JOIN positions p ON pp.position_id = p.id
        """)
        all_prerequisites = cursor.fetchall()

        # ✅ Group by position
        positions = {}
        for row in all_prerequisites:
            pos_id = row['position_id']
            preq_id = int(row['prerequisite_id'])
            weight = row['weight']
            type_ = prerequisite_info.get(preq_id)

            if not type_ or type_ == "Major":
                continue

            if pos_id not in positions:
                positions[pos_id] = {
                    "position_name": row['position_name'],
                    "min_fit_score": row['min_fit_score'] or 0,
                    "subjects": [],
                    "technical_skills": [],
                    "non_technical_skills": []
                }

            if type_ == "Subject":
                positions[pos_id]["subjects"].append((preq_id, weight))
            elif type_ == "Technical Skill":
                positions[pos_id]["technical_skills"].append((preq_id, weight))
            elif type_ == "Non-Technical Skill":
                positions[pos_id]["non_technical_skills"].append((preq_id, weight))

        # ✅ Analyze matches
        final_output = []

        for pos_id, pos_data in positions.items():
            current_app.logger.info(f"=== Checking Position: {pos_data['position_name']} (ID: {pos_id}) ===")
            current_app.logger.info(f"Subjects required: {pos_data['subjects']}")
            current_app.logger.info(f"Technical Skills required: {pos_data['technical_skills']}")
            current_app.logger.info(f"Non-Technical Skills required: {pos_data['non_technical_skills']}")

            # Total and matched weights
            total_subject_weight = sum(weight for _, weight in pos_data['subjects'])
            total_tech_weight = sum(weight for _, weight in pos_data['technical_skills'])
            total_nontech_weight = sum(weight for _, weight in pos_data['non_technical_skills'])

            matched_subject_weight = sum(weight for prereq_id, weight in pos_data['subjects'] if prereq_id in subject_ids)
            matched_tech_weight = sum(weight for prereq_id, weight in pos_data['technical_skills'] if prereq_id in tech_skills)
            matched_nontech_weight = sum(weight for prereq_id, weight in pos_data['non_technical_skills'] if prereq_id in non_tech_skills)

            total_weight = total_subject_weight + total_tech_weight + total_nontech_weight
            matched_weight = matched_subject_weight + matched_tech_weight + matched_nontech_weight

            current_app.logger.info(f"Matched subject weight: {matched_subject_weight}/{total_subject_weight}")
            current_app.logger.info(f"Matched tech weight: {matched_tech_weight}/{total_tech_weight}")
            current_app.logger.info(f"Matched nontech weight: {matched_nontech_weight}/{total_nontech_weight}")
            current_app.logger.info(f"Total matched weight: {matched_weight}/{total_weight}")

            if pos_data['min_fit_score'] <= 0:
                continue

            fit_level = get_fit_level(matched_weight, pos_data['min_fit_score'])
            is_recommended = matched_weight >= pos_data['min_fit_score']

            if is_recommended:
                result = {
                    "position_id": pos_id,
                    "position_name": pos_data['position_name'],
                    "match_score": matched_weight,
                    "match_score_percentage": round((matched_weight / total_weight) * 100, 2) if total_weight else 0,  # ✅ NEW LINE
                    "fit_level": fit_level,
                    "overall_fit_percentage": round((matched_weight / total_weight) * 100, 2) if total_weight else 0,
                    "subject_fit_percentage": round((matched_subject_weight / total_subject_weight) * 100, 2) if total_subject_weight else 0,
                    "technical_skill_fit_percentage": round((matched_tech_weight / total_tech_weight) * 100, 2) if total_tech_weight else 0,
                    "non_technical_skill_fit_percentage": round((matched_nontech_weight / total_nontech_weight) * 100, 2) if total_nontech_weight else 0
                }
                final_output.append(result)

            current_app.logger.info(f"✅ Finished analyzing position {pos_data['position_name']}.\n")

        # Sort results by highest score
        final_output.sort(key=lambda x: x['match_score'], reverse=True)
        fallback_triggered = len(final_output) == 0

        if fallback_triggered:
            return jsonify({
                "success": True,
                "fallback_triggered": True,
                "message": "No positions matched, please add more skills."
            }), 200

        return jsonify({
            "success": True,
            "fallback_possible": False,
            "fallback_triggered": False,
            "recommended_positions": final_output
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    finally:
        connection.close()
