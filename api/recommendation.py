from flask import Blueprint, request, jsonify, current_app
from api.db import get_db_connection

recommendation_routes = Blueprint('recommendation', __name__)

# ✅ Input validation
def validate_user_input(subject_ids, tech_skills, non_tech_skills, is_fallback=False):
    if not is_fallback:
        if not 3 <= len(subject_ids) <= 7:
            return "Please select between 3 and 7 subjects."
        if not 3 <= len(tech_skills) <= 8:
            return "Please select between 3 and 8 technical skills."
        if not 3 <= len(non_tech_skills) <= 5:
            return "Please select between 3 and 5 non-technical skills."
    else:
        if len(subject_ids) == 0 and len(tech_skills) == 0 and len(non_tech_skills) == 0:
            return "Please select at least one skill or subject to improve your result."
    return None

# ✅ Mentor’s scoring logic
def get_fit_level(score, base):
    if score < base * 0.75:
        return "No Match"
    elif score < base:
        return "Fallback"
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
    try:
        data = request.get_json()
        subject_ids = set(data.get("subjects", []))
        tech_skills = set(data.get("technical_skills", []))
        non_tech_skills = set(data.get("non_technical_skills", []))

        # Optional: Preferences (if needed)
        preferences = data.get("advanced_preferences", {})

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Load all prerequisite types
        cursor.execute("SELECT id, type FROM prerequisites")
        types = {int(row['id']): row['type'] for row in cursor.fetchall()}

        # Load position-prerequisites and positions
        cursor.execute("""
            SELECT pp.position_id, pp.prerequisite_id, pp.weight,
                   p.name AS position_name, p.min_fit_score
            FROM position_prerequisites pp
            JOIN positions p ON pp.position_id = p.id
        """)
        raw_data = cursor.fetchall()

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

        # Match logic
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
                continue

            match_level = get_fit_level(matched_weight, base)
            if match_level != "No Match":
                results.append({
                    "position_id": pid,
                    "position_name": pos["position_name"],
                    "match_percentage": round((matched_weight / base) * 100, 2),
                    "match_level": match_level
                })

        return jsonify({"success": True, "results": results}), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()


@recommendation_routes.route('/companies-for-positions', methods=['GET'])
def get_companies_for_positions():
    try:
        position_ids_raw = request.args.get('ids')
        if not position_ids_raw:
            return jsonify({"success": False, "message": "Missing position IDs."}), 400

        # ✅ Parse position IDs safely
        position_ids = [int(pid.strip()) for pid in position_ids_raw.split(',') if pid.strip().isdigit()]
        if not position_ids:
            return jsonify({"success": False, "message": "No valid position IDs provided."}), 400

        # ✅ Optional filters
        training_modes_raw = request.args.get('training_modes', '').strip()
        company_sizes_raw = request.args.get('company_sizes', '').strip()
        industries_raw = request.args.get('industries', '').strip()

        # ✅ If all are empty → user skipped preferences
        if not training_modes_raw and not company_sizes_raw and not industries_raw:
            return jsonify({
                "success": True,
                "companies": []
            }), 200

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        filters = ["cp.position_id IN ({})".format(','.join(['%s'] * len(position_ids)))]
        params = list(position_ids)

        if training_modes_raw:
            mode_ids = [int(x.strip()) for x in training_modes_raw.split(',') if x.strip().isdigit()]
            if mode_ids:
                filters.append("c.training_mode_id IN ({})".format(','.join(['%s'] * len(mode_ids))))
                params.extend(mode_ids)

        if company_sizes_raw:
            size_ids = [int(x.strip()) for x in company_sizes_raw.split(',') if x.strip().isdigit()]
            if size_ids:
                filters.append("c.company_sizes_id IN ({})".format(','.join(['%s'] * len(size_ids))))
                params.extend(size_ids)

        if industries_raw:
            ind_ids = [int(x.strip()) for x in industries_raw.split(',') if x.strip().isdigit()]
            if ind_ids:
                filters.append("c.industry_id IN ({})".format(','.join(['%s'] * len(ind_ids))))
                params.extend(ind_ids)

        # ✅ Query to fetch clean company data
        query = f"""
            SELECT 
                DISTINCT c.id AS company_id,
                c.company_name,
                cs.description AS company_size,
                i.name AS industry,
                tm.description AS training_mode,
                b.city AS location,
                b.address,
                b.website_link
            FROM companies c
            JOIN company_positions cp ON c.id = cp.company_id
            JOIN company_sizes cs ON c.company_sizes_id = cs.id
            JOIN industries i ON c.industry_id = i.id
            JOIN training_modes tm ON c.training_mode_id = tm.id
            JOIN branches b ON c.id = b.company_id AND b.is_main_branch = 1
            WHERE {" AND ".join(filters)}
        """

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        return jsonify({
            "success": True,
            "companies": rows
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.error(f"❌ Error fetching companies for positions: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()

@recommendation_routes.route('/recommendations/fallback-prerequisites', methods=['POST'])
def get_fallback_prerequisites():
    try:
        data = request.get_json()
        subject_ids = set(data.get("subjects", []))
        tech_skills = set(data.get("technical_skills", []))
        non_tech_skills = set(data.get("non_technical_skills", []))

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Load prerequisite types
        cursor.execute("SELECT id, type FROM prerequisites")
        types = {int(row['id']): row['type'] for row in cursor.fetchall()}

        # Load positions and prerequisites
        cursor.execute("""
            SELECT pp.position_id, pp.prerequisite_id, pp.weight,
                   p.name AS position_name, p.min_fit_score
            FROM position_prerequisites pp
            JOIN positions p ON pp.position_id = p.id
        """)
        raw_data = cursor.fetchall()

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

        # Identify fallback-only positions
        fallback_positions = []
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
                continue

            fit_level = get_fit_level(matched_weight, base)
            if fit_level == "Fallback":
                fallback_positions.append((pid, pos, matched))

        if not fallback_positions:
            return jsonify({"success": False, "message": "No fallback positions found."}), 404

        # Pick the top fallback position (first in list)
        top_pid, top_pos, top_matched = fallback_positions[0]

        # Collect missing prerequisite IDs
        missing_subjects = [pid_ for pid_, _ in top_pos["subjects"] if pid_ not in subject_ids]
        missing_tech_skills = [pid_ for pid_, _ in top_pos["technical_skills"] if pid_ not in tech_skills]
        missing_non_tech_skills = [pid_ for pid_, _ in top_pos["non_technical_skills"] if pid_ not in non_tech_skills]

        return jsonify({
            "success": True,
            "position_id": top_pid,
            "position_name": top_pos["position_name"],
            "missing_prerequisites": {
                "subjects": missing_subjects,
                "technical_skills": missing_tech_skills,
                "non_technical_skills": missing_non_tech_skills
            },
            "current_selections": {
                "subjects": list(subject_ids),
                "technical_skills": list(tech_skills),
                "non_technical_skills": list(non_tech_skills)
            }
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection.is_connected():
            connection.close()
