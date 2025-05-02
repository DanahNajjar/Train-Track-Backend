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

# ✅ Mentor’s scoring logic — dynamic tiers based on min_fit_score
def get_fit_level(score, base):
    if score < base * 0.75:
        return "No Match"
    elif score < base:
        return "Fallback Only"
    elif score < base * 1.25:
        return "Partial Match"
    elif score < base * 1.5:
        return "Strong Match"
    elif score < base * 1.75:
        return "Very Strong Match"
    else:
        return "Perfect Match"

@recommendation_routes.route('/recommendations', methods=['POST'])
def get_recommendations():
    current_app.logger.info("🚀 Starting recommendation processing...")
    data = request.get_json()

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Extract user input
        subject_ids = set(data.get("subjects", []))
        tech_skills = set(data.get("technical_skills", []))
        non_tech_skills = set(data.get("non_technical_skills", []))

        current_app.logger.info(f"Subjects: {subject_ids}")
        current_app.logger.info(f"Tech Skills: {tech_skills}")
        current_app.logger.info(f"Non-Tech Skills: {non_tech_skills}")

        error = validate_user_input(subject_ids, tech_skills, non_tech_skills)
        if error:
            return jsonify({"success": False, "message": error}), 400

        # ✅ Load prerequisite types
        cursor.execute("SELECT id, type FROM prerequisites")
        types = {int(row['id']): row['type'] for row in cursor.fetchall()}

        # ✅ Load position prerequisites and scores
        cursor.execute("""
            SELECT pp.position_id, pp.prerequisite_id, pp.weight,
                   p.name AS position_name, p.min_fit_score
            FROM position_prerequisites pp
            JOIN positions p ON pp.position_id = p.id
        """)
        raw_data = cursor.fetchall()

        # ✅ Group prerequisites by position
        positions = {}
        for row in raw_data:
            pid = row['position_id']
            preq_id = int(row['prerequisite_id'])
            weight = row['weight']
            type_ = types.get(preq_id)

            if not type_ or type_ == "Major":
                continue

            if pid not in positions:
                positions[pid] = {
                    "position_name": row['position_name'],
                    "min_fit_score": row['min_fit_score'],
                    "subjects": [],
                    "technical_skills": [],
                    "non_technical_skills": []
                }

            positions[pid][{
                "Subject": "subjects",
                "Technical Skill": "technical_skills",
                "Non-Technical Skill": "non_technical_skills"
            }[type_]].append((preq_id, weight))

        # ✅ Calculate fit scores
        results = []
        for pid, pos in positions.items():
            total = {
                "subjects": sum(w for _, w in pos["subjects"]),
                "technical_skills": sum(w for _, w in pos["technical_skills"]),
                "non_technical_skills": sum(w for _, w in pos["non_technical_skills"])
            }

            matched = {
                "subjects": sum(w for pid_, w in pos["subjects"] if pid_ in subject_ids),
                "technical_skills": sum(w for pid_, w in pos["technical_skills"] if pid_ in tech_skills),
                "non_technical_skills": sum(w for pid_, w in pos["non_technical_skills"] if pid_ in non_tech_skills)
            }

            total_weight = sum(total.values())
            matched_weight = sum(matched.values())

            if total_weight == 0 or matched_weight == 0:
                continue

            base = pos["min_fit_score"]
            if not base:
                continue  # Skip positions without min_fit_score

            fit_level = get_fit_level(matched_weight, base)
            if fit_level in ["No Match", "Fallback Only"]:
                continue

            overall_pct = round((matched_weight / total_weight) * 100, 2)

            results.append({
                "position_id": pid,
                "position_name": pos["position_name"],
                "match_score": matched_weight,
                "match_score_percentage": overall_pct,
                "fit_level": fit_level,
                "overall_fit_percentage": overall_pct,
                "subject_fit_percentage": round((matched["subjects"] / total["subjects"]) * 100, 2) if total["subjects"] else 0,
                "technical_skill_fit_percentage": round((matched["technical_skills"] / total["technical_skills"]) * 100, 2) if total["technical_skills"] else 0,
                "non_technical_skill_fit_percentage": round((matched["non_technical_skills"] / total["non_technical_skills"]) * 100, 2) if total["non_technical_skills"] else 0
            })

        results.sort(key=lambda x: x['match_score'], reverse=True)

        return jsonify({
            "success": True,
            "fallback_possible": False,
            "fallback_triggered": len(results) == 0,
            "recommended_positions": results
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.error(f"❌ Error: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection.is_connected():
            connection.close()
