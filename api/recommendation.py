from flask import Blueprint, request, jsonify
from api.db import get_db_connection

recommendation_routes = Blueprint('recommendation', __name__)

# 🔹 Validation helper function
def validate_user_input(subject_ids, tech_skills, non_tech_skills):
    if len(subject_ids) < 3:
        return "Please select at least 3 subjects."
    if not 3 <= len(tech_skills) <= 10:
        return "Please select between 3 and 10 technical skills."
    if not 3 <= len(non_tech_skills) <= 5:
        return "Please select between 3 and 5 non-technical skills."
    return None

@recommendation_routes.route('/recommendations', methods=['POST'])
def get_recommendations():
    data = request.get_json()
    debug_mode = request.args.get('debug', 'false') == 'true'

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Extract inputs
        major_id = data.get("major_id")
        subject_ids = set(data.get("subjects", []))
        tech_skills = set(data.get("technical_skills", []))
        non_tech_skills = set(data.get("non_technical_skills", []))
        preferences = data.get("preferences", {})

        # ✅ Validate inputs
        validation_error = validate_user_input(subject_ids, tech_skills, non_tech_skills)
        if validation_error:
            return jsonify({"success": False, "message": validation_error}), 400

        # Step 1: Fetch all position prerequisites
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

        # Step 2: Organize scores
        position_scores = {}
        for row in all_data:
            pos_id = row['position_id']
            preq_id = row['prerequisite_id']
            weight = row['weight']
            preq_type = row['type']

            if pos_id not in position_scores:
                position_scores[pos_id] = {
                    'subject_total': 0, 'subject_matched': 0,
                    'tech_total': 0, 'tech_matched': 0,
                    'nontech_total': 0, 'nontech_matched': 0
                }

            if preq_type == "Subject":
                position_scores[pos_id]['subject_total'] += weight
                if preq_id in subject_ids:
                    position_scores[pos_id]['subject_matched'] += weight
            elif preq_type == "Technical Skill":
                position_scores[pos_id]['tech_total'] += weight
                if preq_id in tech_skills:
                    position_scores[pos_id]['tech_matched'] += weight
            elif preq_type == "Non-Technical Skill":
                position_scores[pos_id]['nontech_total'] += weight
                if preq_id in non_tech_skills:
                    position_scores[pos_id]['nontech_matched'] += weight

        # Step 3: Calculate scores
        results = []
        for pos_id, score_data in position_scores.items():
            s_total = score_data['subject_total']
            t_total = score_data['tech_total']
            n_total = score_data['nontech_total']

            s_matched = score_data['subject_matched']
            t_matched = score_data['tech_matched']
            n_matched = score_data['nontech_matched']

            subject_score = ((s_matched / s_total) if s_total else 0) * 50
            tech_score = ((t_matched / t_total) if t_total else 0) * 30
            nontech_score = ((n_matched / n_total) if n_total else 0) * 20

            matched_components = sum([
                1 if s_matched > 0 else 0,
                1 if t_matched > 0 else 0,
                1 if n_matched > 0 else 0
            ])
            category_bonus = 3 if matched_components >= 2 else 0

            raw_score = subject_score + tech_score + nontech_score + category_bonus
            total_score = min(round(raw_score * 1.5, 2), 100)

            result = {
                'position_id': pos_id,
                'match_score': total_score
            }

            # ✅ Include debug info if enabled
            if debug_mode:
                result["debug"] = {
                    "subject_score": round(subject_score, 2),
                    "tech_score": round(tech_score, 2),
                    "nontech_score": round(nontech_score, 2),
                    "category_bonus": category_bonus,
                    "raw_score_before_scaling": round(raw_score, 2),
                    "final_scaled_score": total_score
                }

            results.append(result)

        # Step 4: Add position names
        cursor.execute("SELECT id, name FROM positions")
        all_positions = {row['id']: row['name'] for row in cursor.fetchall()}

        final_output = []
        for r in results:
            final_output.append({
                'position_id': r['position_id'],
                'position_name': all_positions.get(r['position_id'], 'Unknown'),
                'match_score': r['match_score'],
                'debug': r.get("debug") if debug_mode else None
            })

        # Sort by match score descending
        final_output.sort(key=lambda x: x['match_score'], reverse=True)

        return jsonify({
            "success": True,
            "recommended_positions": final_output
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
