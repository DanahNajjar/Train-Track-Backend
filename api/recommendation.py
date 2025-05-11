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
    from flask import session
    import json  # ✅ make sure it's at the top

    current_app.logger.info("🔥 /recommendations route HIT")
    current_app.logger.info("🚀 Starting recommendation processing...")

    # ✅ Get data
    data = request.get_json()

    # ✅ Fix: if "subjects" is passed as a string (e.g. "170,171,176"), convert it to a list
    if isinstance(data.get("subjects"), str):
        try:
            data["subjects"] = json.loads(data["subjects"])
        except:
            data["subjects"] = []

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Safely extract inputs as sets
        subject_ids = set(data.get("subjects", []))
        tech_skills = set(data.get("technical_skills", []))
        non_tech_skills = set(data.get("non_technical_skills", []))
        previous_fallback_ids = set(data.get("previous_fallback_ids", []))
        was_fallback_promoted = False
        no_matches = []

        # ✅ Advanced preferences
        advanced_preferences = data.get("advanced_preferences", {})
        has_preferences = any([
            advanced_preferences.get("training_modes"),
            advanced_preferences.get("company_sizes"),
            advanced_preferences.get("industries")
        ])

        current_app.logger.info(f"Subjects: {subject_ids}")
        current_app.logger.info(f"Tech Skills: {tech_skills}")
        current_app.logger.info(f"Non-Tech Skills: {non_tech_skills}")

        # ✅ Validate
        is_fallback = bool(data.get("is_fallback", False)) or bool(previous_fallback_ids)
        error = validate_user_input(subject_ids, tech_skills, non_tech_skills, is_fallback)
        if error:
            return jsonify({"success": False, "message": error}), 400

        # ✅ Load prerequisite types
        cursor.execute("SELECT id, type FROM prerequisites")
        types = {int(row['id']): row['type'] for row in cursor.fetchall()}

        # ✅ Load all positions and prerequisites
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

            category = {
                "Subject": "subjects",
                "Technical Skill": "technical_skills",
                "Non-Technical Skill": "non_technical_skills"
            }[type_]

            positions[pid][category].append((preq_id, weight))

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

            fit_level = get_fit_level(matched_weight, base)

            if fit_level == "No Match":
                no_matches.append({
                    "fit_level": fit_level,
                    "match_score_percentage": round((matched_weight / total_weight) * 100, 2),
                    "position_id": pid,
                    "position_name": pos["position_name"],
                    "subject_fit_percentage": round((matched["subjects"] / total["subjects"]) * 100, 2) if total["subjects"] else 0,
                    "technical_skill_fit_percentage": round((matched["technical_skills"] / total["technical_skills"]) * 100, 2) if total["technical_skills"] else 0,
                    "non_technical_skill_fit_percentage": round((matched["non_technical_skills"] / total["non_technical_skills"]) * 100, 2) if total["non_technical_skills"] else 0
                })
                continue

            if fit_level != "Fallback" and pid in previous_fallback_ids:
                was_fallback_promoted = True

            current_app.logger.info(
                f"[{pos['position_name']}] Match Score: {matched_weight} | "
                f"Min Fit: {base} | Fit Level: {fit_level} | Total Weight: {total_weight}"
            )

            overall_pct = round((matched_weight / total_weight) * 100, 2)

            results.append({
                "fit_level": fit_level,
                "match_score_percentage": overall_pct,
                "position_id": pid,
                "position_name": pos["position_name"],
                "subject_fit_percentage": round((matched["subjects"] / total["subjects"]) * 100, 2) if total["subjects"] else 0,
                "technical_skill_fit_percentage": round((matched["technical_skills"] / total["technical_skills"]) * 100, 2) if total["technical_skills"] else 0,
                "non_technical_skill_fit_percentage": round((matched["non_technical_skills"] / total["non_technical_skills"]) * 100, 2) if total["non_technical_skills"] else 0,
                "was_promoted_from_fallback": pid in previous_fallback_ids and fit_level != "Fallback"
            })

        results.sort(key=lambda x: x['match_score_percentage'], reverse=True)
        session["recommended_positions"] = [r["position_id"] for r in results]

        fallbacks = [r for r in results if r["fit_level"] == "Fallback"]
        strong_matches = [r for r in results if r["fit_level"] != "Fallback"]

        if strong_matches:
            return jsonify({
                "success": True,
                "fallback_possible": False,
                "fallback_triggered": False,
                "was_fallback_promoted": was_fallback_promoted,
                "recommended_positions": strong_matches,
                "should_fetch_companies": has_preferences
            }), 200

        elif fallbacks:
            return jsonify({
                "success": True,
                "fallback_possible": True,
                "fallback_triggered": True,
                "was_fallback_promoted": False,
                "recommended_positions": fallbacks,
                "should_fetch_companies": has_preferences
            }), 200

        elif no_matches:
            return jsonify({
                "success": True,
                "fallback_possible": False,
                "fallback_triggered": False,
                "was_fallback_promoted": False,
                "recommended_positions": [],
                "no_match_positions": no_matches,
                "should_fetch_companies": has_preferences
            }), 200

        return jsonify({
            "success": True,
            "fallback_possible": False,
            "fallback_triggered": False,
            "was_fallback_promoted": False,
            "recommended_positions": [],
            "should_fetch_companies": has_preferences
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.error(f"❌ Error: {str(e)}")
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
            }
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection.is_connected():
            connection.close()
from flask import request, jsonify, session  # ✅ FIXED: added session import

DEBUG_BYPASS_SESSION = True  # 🔁 Set to False in production to enforce session

@recommendation_routes.route('/position/<int:position_id>', methods=['GET'])
def get_position_details(position_id):
    connection = None
    try:
        if not DEBUG_BYPASS_SESSION:
            allowed_ids = session.get("recommended_positions")
            if allowed_ids is not None and position_id not in allowed_ids:
                return jsonify({
                    "success": False,
                    "message": "Access denied. This position was not recommended."
                }), 403

        # ✅ Connect to DB
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Get position info
        cursor.execute("""
            SELECT name, description, tasks, tips
            FROM positions
            WHERE id = %s
        """, (position_id,))
        position = cursor.fetchone()
        if not position:
            return jsonify({"success": False, "message": "Position not found."}), 404

        tasks = position["tasks"].split("\n") if position["tasks"] else []

        # ✅ Subjects
        cursor.execute("""
            SELECT p.name
            FROM position_prerequisites pp
            JOIN prerequisites p ON pp.prerequisite_id = p.id
            WHERE pp.position_id = %s AND p.type = 'Subject'
        """, (position_id,))
        subjects = [row["name"] for row in cursor.fetchall()]

        # ✅ Technical Skills
        cursor.execute("""
            SELECT p.name
            FROM position_prerequisites pp
            JOIN prerequisites p ON pp.prerequisite_id = p.id
            WHERE pp.position_id = %s AND p.type = 'Technical Skill'
        """, (position_id,))
        technical_skills = [row["name"] for row in cursor.fetchall()]

        # ✅ Non-Technical Skills
        cursor.execute("""
            SELECT p.name
            FROM position_prerequisites pp
            JOIN prerequisites p ON pp.prerequisite_id = p.id
            WHERE pp.position_id = %s AND p.type = 'Non-Technical Skill'
        """, (position_id,))
        non_technical_skills = [row["name"] for row in cursor.fetchall()]

        # ✅ Resources
        cursor.execute("""
            SELECT resource_type, title, url
            FROM learning_resources
            WHERE position_id = %s
        """, (position_id,))
        resources = cursor.fetchall()

        return jsonify({
            "success": True,
            "position_name": position["name"],
            "description": position["description"],
            "tasks": tasks,
            "tips": position["tips"],
            "subjects": subjects,
            "technical_skills": technical_skills,
            "non_technical_skills": non_technical_skills,
            "resources": resources
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


@recommendation_routes.route('/debug/set-session', methods=['POST'])
def set_debug_session():
    from flask import session
    try:
        data = request.get_json()
        position_ids = data.get("position_ids", [])
        if not isinstance(position_ids, list):
            return jsonify({"success": False, "message": "Invalid format. Send a list of position IDs."}), 400

        session["recommended_positions"] = position_ids
        return jsonify({
            "success": True,
            "message": f"Session updated with position IDs: {position_ids}"
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

