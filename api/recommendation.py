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

# ✅ Fit Level Helper
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

        # ✅ Combine all selected prerequisite IDs to avoid double-counting
        all_selected_ids = subject_ids.union(tech_skills).union(non_tech_skills)

        # ✅ Validate input lengths
        validation_error = validate_user_input(subject_ids, tech_skills, non_tech_skills)
        if validation_error:
            return jsonify({"success": False, "message": validation_error}), 400

        # ✅ Step 1: Fetch all prerequisite weights
        cursor.execute("""
            SELECT 
                pp.position_id,
                pp.prerequisite_id,
                pp.weight,
                p.type
            FROM position_prerequisites pp
            JOIN prerequisites p ON pp.prerequisite_id = p.id
        """)
        all_data = cursor.fetchall()

        # ✅ Step 2: Sum matched weights per position
        position_scores = {}
        for row in all_data:
            pos_id = row['position_id']
            preq_id = row['prerequisite_id']
            weight = row['weight']

            if pos_id not in position_scores:
                position_scores[pos_id] = {
                    "matched_weight": 0,
                    "total_weight": 0
                }

            position_scores[pos_id]['total_weight'] += weight

            if preq_id in all_selected_ids:
                position_scores[pos_id]['matched_weight'] += weight

        # ✅ Step 3: Load positions with min_fit_score
        cursor.execute("SELECT id, name, min_fit_score FROM positions")
        all_positions = {
            row['id']: {
                'name': row['name'],
                'min_fit_score': row['min_fit_score'] or 0
            } for row in cursor.fetchall()
        }

        # ✅ Step 4: Build final output only for positions that meet min_fit_score
        final_output = []
        for pos_id, score_data in position_scores.items():
            matched_score = score_data['matched_weight']
            total_score = score_data['total_weight']
            position = all_positions.get(pos_id)

            if not position:
                continue

            # ❌ Skip positions with no min_fit_score
            if position['min_fit_score'] <= 0:
                continue

            # ❌ Skip positions that don't meet the threshold
            if matched_score < position['min_fit_score']:
                continue

            fit_level = get_fit_level(matched_score, position['min_fit_score'])

            result = {
                'position_id': pos_id,
                'position_name': position['name'],
                'match_score': matched_score,
                'fit_level': fit_level
            }

            if debug_mode:
                result['debug'] = {
                    'matched_score': matched_score,
                    'total_required_score': total_score,
                    'min_fit_score': position['min_fit_score'],
                    'fit_level': fit_level,
                    'percentage_of_total': round((matched_score / total_score) * 100, 2) if total_score > 0 else 0
                }

            final_output.append(result)

        final_output.sort(key=lambda x: x['match_score'], reverse=True)

        if debug_mode:
            print("\n🔍 Match Results (Filtered & Cleaned):")
            for r in final_output:
                print(f"📌 {r['position_name']} — {r['match_score']} [{r['fit_level']}]")

        return jsonify({
            "success": True,
            "recommended_positions": final_output
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
