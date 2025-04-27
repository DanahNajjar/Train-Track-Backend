from flask import Blueprint, request, jsonify
from api.db import get_db_connection

recommendation_routes = Blueprint('recommendation', __name__)

# ✅ Validation helper
def validate_user_input(subject_ids, tech_skills, non_tech_skills):
    if not 3 <= len(subject_ids) <= 7:
        return "Please select between 3 and 7 subjects."
    if not 3 <= len(tech_skills) <= 8:
        return "Please select between 3 and 8 technical skills."
    if not 3 <= len(non_tech_skills) <= 5:
        return "Please select between 3 and 5 non-technical skills."
    return None

# ✅ Fit Level helper
def get_fit_level(matched_score, min_fit_score):
    if matched_score >= min_fit_score * 1.25:
        return "Perfect Match"
    elif matched_score >= min_fit_score:
        return "Partial Match"
    else:
        return "No Match"

# ✅ Main Recommendation Endpoint
@recommendation_routes.route('/recommendations', methods=['POST'])
def get_recommendations():
    data = request.get_json()
    debug_mode = request.args.get('debug', 'false') == 'true'

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Extract Inputs
        subject_ids = set(data.get("subjects", []))
        tech_skills = set(data.get("technical_skills", []))
        non_tech_skills = set(data.get("non_technical_skills", []))
        all_selected_ids = subject_ids.union(tech_skills).union(non_tech_skills)

        # ✅ Validate Inputs
        validation_error = validate_user_input(subject_ids, tech_skills, non_tech_skills)
        if validation_error:
            return jsonify({"success": False, "message": validation_error}), 400

        # ✅ Fetch prerequisite weights + positions together
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
        all_data = cursor.fetchall()

        # ✅ Fetch prerequisite types (correctly using `type`)
        cursor.execute("SELECT id, type FROM prerequisites")
        prerequisite_types = {row['id']: row['type'] for row in cursor.fetchall()}

        # ✅ Prepare scoring
        position_scores = {}
        for row in all_data:
            pos_id = row['position_id']
            preq_id = row['prerequisite_id']
            weight = row['weight']
            pos_name = row['position_name']
            min_fit_score = row['min_fit_score'] or 0
            preq_type = prerequisite_types.get(preq_id)

            if pos_id not in position_scores:
                position_scores[pos_id] = {
                    "position_name": pos_name,
                    "min_fit_score": min_fit_score,
                    "matched_weight": 0,
                    "total_weight": 0,
                    "subject_matched_weight": 0,
                    "subject_total_weight": 0,
                    "tech_matched_weight": 0,
                    "tech_total_weight": 0,
                    "nontech_matched_weight": 0,
                    "nontech_total_weight": 0
                }

            position_scores[pos_id]['total_weight'] += weight

            # Group weights
            if preq_type == "Subject":
                position_scores[pos_id]['subject_total_weight'] += weight
            elif preq_type == "Technical Skill":
                position_scores[pos_id]['tech_total_weight'] += weight
            elif preq_type == "Non-Technical Skill":
                position_scores[pos_id]['nontech_total_weight'] += weight

            if preq_id in all_selected_ids:
                position_scores[pos_id]['matched_weight'] += weight
                if preq_type == "Subject":
                    position_scores[pos_id]['subject_matched_weight'] += weight
                elif preq_type == "Technical Skill":
                    position_scores[pos_id]['tech_matched_weight'] += weight
                elif preq_type == "Non-Technical Skill":
                    position_scores[pos_id]['nontech_matched_weight'] += weight

        # ✅ Analyze matches
        final_output = []
        unmatched_positions = []

        for pos_id, data in position_scores.items():
            matched_score = data['matched_weight']
            total_score = data['total_weight']
            min_fit_score = data['min_fit_score']
            pos_name = data['position_name']

            if min_fit_score <= 0:
                continue  # Ignore irrelevant positions

            fit_level = get_fit_level(matched_score, min_fit_score)
            is_recommended = matched_score >= min_fit_score

            debug_info = {
                'position_name': pos_name,
                'matched_score': matched_score,
                'total_required_score': total_score,
                'min_fit_score': min_fit_score,
                'percentage_of_total': round((matched_score / total_score) * 100, 2) if total_score else 0,
                'match_vs_min_score_percent': round((matched_score / min_fit_score) * 100, 2) if min_fit_score else 0,
                'fit_level': fit_level,
                'recommended': is_recommended,
                'reason': "✓ Recommended" if is_recommended else "✗ Not Recommended — below min_fit_score"
            }

            if is_recommended:
                result = {
                    'position_id': pos_id,
                    'position_name': pos_name,
                    'match_score': matched_score,
                    'fit_level': fit_level,
                    'overall_fit_percentage': round((matched_score / total_score) * 100, 2) if total_score else 0,
                    'subject_fit_percentage': round((data['subject_matched_weight'] / data['subject_total_weight']) * 100, 2) if data['subject_total_weight'] else 0,
                    'technical_skill_fit_percentage': round((data['tech_matched_weight'] / data['tech_total_weight']) * 100, 2) if data['tech_total_weight'] else 0,
                    'non_technical_skill_fit_percentage': round((data['nontech_matched_weight'] / data['nontech_total_weight']) * 100, 2) if data['nontech_total_weight'] else 0
                }
                if debug_mode:
                    result['debug'] = debug_info
                final_output.append(result)
            else:
                unmatched_positions.append({
                    'position_name': pos_name,
                    'matched_score': matched_score,
                    'min_fit_score': min_fit_score
                })

            if debug_mode:
                print(f"\n📌 {pos_name} — Score: {matched_score}/{total_score}")
                print(f"   ➤ Fit Level: {fit_level} — {debug_info['reason']}")

        # ✅ Sort matches
        final_output.sort(key=lambda x: x['match_score'], reverse=True)

        # ✅ Check fallback
        fallback_triggered = len(final_output) == 0

        if fallback_triggered:
            if debug_mode:
                print("\n⚠️ No positions met min_fit_score — fallback triggered.")
            return jsonify({
                "note": "💡 No positions matched your selections.",
                "suggestion": "Consider selecting more relevant subjects or skills to improve your match.",
                "fallback_possible": True,
                "fallback_triggered": True,
                "unmatched_positions": unmatched_positions,
                "recommended_positions": [],
                "success": True
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
