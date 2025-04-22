from flask import Blueprint, request, jsonify
from api.db import get_db_connection

recommendation_routes = Blueprint('recommendation', __name__)

def validate_user_input(subject_ids, tech_skills, non_tech_skills):
    if len(subject_ids) < 3:
        return "Please select at least 3 subjects."
    if not 3 <= len(tech_skills) <= 10:
        return "Please select between 3 and 10 technical skills."
    if not 3 <= len(non_tech_skills) <= 5:
        return "Please select between 3 and 5 non-technical skills."
    return None

def get_fit_level(score):
    if score >= 90:
        return "Perfect Fit"
    elif score >= 70:
        return "Good Fit"
    elif score >= 50:
        return "Moderate Fit"
    else:
        return "Low Fit"

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
            preq_type = row['type']

            if pos_id not in position_scores:
                position_scores[pos_id] = {
                    "matched_weight": 0,
                    "total_weight": 0
                }

            position_scores[pos_id]['total_weight'] += weight

            if (
                (preq_type == "Subject" and preq_id in subject_ids) or
                (preq_type == "Technical Skill" and preq_id in tech_skills) or
                (preq_type == "Non-Technical Skill" and preq_id in non_tech_skills)
            ):
                position_scores[pos_id]['matched_weight'] += weight

        # ✅ Step 3: Load positions with min_fit_score
        cursor.execute("SELECT id, name, min_fit_score FROM positions")
        all_positions = {
            row['id']: {
                'name': row['name'],
                'min_fit_score': row['min_fit_score']
            } for row in cursor.fetchall()
        }

        final_output = []
        for pos_id, score_data in position_scores.items():
            matched_score = score_data['matched_weight']
            total_score = score_data['total_weight']
            position = all_positions.get(pos_id)

            if not position:
                continue

            if matched_score >= position['min_fit_score']:
                percentage_score = round((matched_score / total_score) * 100, 2) if total_score > 0 else 0
                fit_level = get_fit_level(percentage_score)

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
                        'percentage_of_total': percentage_score
                    }

                final_output.append(result)

        # ✅ Sort by matched score descending
        final_output.sort(key=lambda x: x['match_score'], reverse=True)

        # ✅ Debug print
        if debug_mode:
            print("\n🔍 Match Results (New Logic):")
            for r in final_output:
                print(f"📌 {r['position_name']} — {r['match_score']} [{r['fit_level']}]")
                if 'debug' in r:
                    print(f"   - Total Required: {r['debug']['total_required_score']}")
                    print(f"   - Min Fit Score: {r['debug']['min_fit_score']}")
                    print(f"   - % of Total: {r['debug']['percentage_of_total']}")

        return jsonify({
            "success": True,
            "recommended_positions": final_output
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

