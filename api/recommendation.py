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

        # ✅ Fetch prerequisite weights
        cursor.execute("""
            SELECT 
                pp.position_id,
                pp.prerequisite_id,
                pp.weight
            FROM position_prerequisites pp
        """)
        all_data = cursor.fetchall()

        # ✅ Sum weights
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

        # ✅ Load positions with min_fit_score
        cursor.execute("SELECT id, name, min_fit_score FROM positions")
        all_positions = {
            row['id']: {
                'name': row['name'],
                'min_fit_score': row['min_fit_score'] or 0
            } for row in cursor.fetchall()
        }

        # ✅ Prepare output
        final_output = []
        unmatched_positions = []

        for pos_id, score_data in position_scores.items():
            matched_score = score_data['matched_weight']
            total_score = score_data['total_weight']
            position = all_positions.get(pos_id)

            if not position or position['min_fit_score'] <= 0:
                continue  # Skip irrelevant positions

            fit_level = get_fit_level(matched_score, position['min_fit_score'])
            is_recommended = matched_score >= position['min_fit_score']
            reason = "✓ Recommended" if is_recommended else "✗ Not Recommended — below min_fit_score"

            # Debug info block
            debug_info = {
                'position_name': position['name'],
                'matched_score': matched_score,
                'total_required_score': total_score,
                'min_fit_score': position['min_fit_score'],
                'percentage_of_total': round((matched_score / total_score) * 100, 2) if total_score > 0 else 0,
                'match_vs_min_score_percent': round((matched_score / position['min_fit_score']) * 100, 2) if position['min_fit_score'] > 0 else 0,
                'fit_level': fit_level,
                'recommended': is_recommended,
                'reason': reason
            }

            if is_recommended:
                result = {
                    'position_id': pos_id,
                    'position_name': position['name'],
                    'match_score': matched_score,
                    'fit_level': fit_level
                }
                if debug_mode:
                    result['debug'] = debug_info
                final_output.append(result)
            else:
                unmatched_positions.append({
                    'position_name': position['name'],
                    'matched_score': matched_score,
                    'min_fit_score': position['min_fit_score']
                })

            if debug_mode:
                print(f"\n📌 {position['name']} — Score: {matched_score}/{total_score}")
                print(f"   ➤ Fit Level: {fit_level} — {reason}")

        final_output.sort(key=lambda x: x['match_score'], reverse=True)

        # ✅ Check if fallback is needed (no positions met min_fit_score)
        fallback_triggered = len(final_output) == 0

        if fallback_triggered:
            if debug_mode:
                print("\n⚠️ No positions met min_fit_score — fallback logic triggered.")
                for entry in unmatched_positions:
                    print(f"   ✗ {entry['position_name']} — {entry['matched_score']} < min_fit {entry['min_fit_score']}")
            return jsonify({
                "note": "💡 No positions matched your selections.",
                "suggestion": "Consider selecting more relevant subjects or skills to improve your match.",
                "fallback_possible": True,
                "fallback_triggered": True,
                "unmatched_positions": unmatched_positions,
                "recommended_positions": [],
                "success": True
            }), 200

        # ✅ Otherwise, return normal recommended positions
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
