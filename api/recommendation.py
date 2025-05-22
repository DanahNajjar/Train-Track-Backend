from flask import Blueprint, request, jsonify, current_app, session
from api.db import get_db_connection
import json

DEBUG_BYPASS_SESSION = True
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
    ratio = score / base
    if ratio < 0.75:
        return "No Match"
    elif ratio < 1.0:
        return "Fallback"
    elif ratio < 1.25:
        return "Partial Match"
    elif ratio < 1.75:
        return "Strong Match"
    elif ratio < 1.9:
        return "Very Strong Match"
    else:
        return "Perfect Match"


@recommendation_routes.route('/', methods=['POST'])
def get_recommendations():

    current_app.logger.info("🔥 /recommendations route HIT")
    current_app.logger.info("🚀 Starting recommendation processing...")

    data = request.get_json()

    user_id = data.get("user_id", "guest_unknown")
    current_app.logger.info(f"🧾 User ID for saving: {user_id}")

    if isinstance(data.get("subjects"), str):
        try:
            data["subjects"] = json.loads(data["subjects"])
        except:
            data["subjects"] = []

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        subject_ids = set(data.get("subjects", []))
        tech_skills = set(data.get("technical_skills", []))
        non_tech_skills = set(data.get("non_technical_skills", []))
        previous_fallback_ids = set(data.get("previous_fallback_ids", []))
        was_fallback_promoted = False

        advanced_preferences = data.get("advanced_preferences", {})
        has_preferences = any([
            advanced_preferences.get("training_modes"),
            advanced_preferences.get("company_sizes"),
            advanced_preferences.get("industries"),
            advanced_preferences.get("company_culture")
        ])

        company_filter_ids = {
            "training_mode": advanced_preferences.get("training_modes"),
            "company_size": advanced_preferences.get("company_sizes"),
            "preferred_industry": advanced_preferences.get("industries", []),
            "company_culture": advanced_preferences.get("company_culture", [])
        }

        current_app.logger.info(f"📘 Subjects: {subject_ids}")
        current_app.logger.info(f"🛠️ Tech Skills: {tech_skills}")
        current_app.logger.info(f"🧠 Non-Tech Skills: {non_tech_skills}")

        is_fallback = bool(data.get("is_fallback", False)) or bool(previous_fallback_ids)
        error = validate_user_input(subject_ids, tech_skills, non_tech_skills, is_fallback)
        if error:
            return jsonify({"success": False, "message": error}), 400

        # Load types
        cursor.execute("SELECT id, type FROM prerequisites")
        types = {int(row['id']): row['type'] for row in cursor.fetchall()}

        # Load position-prerequisite mapping
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

            # ✅ NEW: Replace match_score_percentage with better visual % (0–100)
            visual_score = round(min((matched_weight / base / 1.5) * 100, 100), 2)

            current_app.logger.info(
                f"🧮 Position: {pos['position_name']} | Matched: {matched_weight} | "
                f"Total: {total_weight} | Min Fit: {base} | Fit Level: {fit_level} | UI Match %: {visual_score}"
            )

            results.append({
                "fit_level": fit_level,
                "match_score_percentage": visual_score,  # ✅ FRONTEND FRIENDLY
                "position_id": pid,
                "position_name": pos["position_name"],
                "subject_fit_percentage": round((matched["subjects"] / total["subjects"]) * 100, 2) if total["subjects"] else 0,
                "technical_skill_fit_percentage": round((matched["technical_skills"] / total["technical_skills"]) * 100, 2) if total["technical_skills"] else 0,
                "non_technical_skill_fit_percentage": round((matched["non_technical_skills"] / total["non_technical_skills"]) * 100, 2) if total["non_technical_skills"] else 0,
                "was_promoted_from_fallback": pid in previous_fallback_ids and fit_level != "Fallback",
                "matched_weight": matched_weight,
                "min_fit_score": base,
                "fit_ratio": round(matched_weight / base * 100, 2)
            })

        results.sort(key=lambda x: x['match_score_percentage'], reverse=True)
        session["recommended_positions"] = [r["position_id"] for r in results]

        perfect_matches = [r for r in results if r["fit_level"] == "Perfect Match"]
        strong_matches = [r for r in results if r["fit_level"] in ["Very Strong Match", "Strong Match", "Partial Match"]]
        fallbacks = [r for r in results if r["fit_level"] == "Fallback"]
        no_matches = [r for r in results if r["fit_level"] == "No Match"]

        recommendation_result = {
            "results": results,
            "fallback_triggered": bool(fallbacks),
            "preferences_used": has_preferences,
            "filters": company_filter_ids
        }

        try:
            cursor.execute("""
                INSERT INTO user_results (user_id, submission_data, result_data)
                VALUES (%s, %s, %s)
            """, (
                user_id,
                json.dumps(data),
                json.dumps(recommendation_result)
            ))
            connection.commit()
            current_app.logger.info("💾 Trial saved to user_results.")
        except Exception as save_err:
            current_app.logger.error(f"❌ Failed to save result: {save_err}")

        if perfect_matches:
            return jsonify({
                "success": True,
                "fallback_possible": False,
                "fallback_triggered": False,
                "was_fallback_promoted": False,
                "recommended_positions": [perfect_matches[0]],
                "should_fetch_companies": has_preferences,
                "company_filter_ids": company_filter_ids
            }), 200

        elif strong_matches:
            return jsonify({
                "success": True,
                "fallback_possible": False,
                "fallback_triggered": False,
                "was_fallback_promoted": False,
                "recommended_positions": strong_matches,
                "should_fetch_companies": has_preferences,
                "company_filter_ids": company_filter_ids
            }), 200

        elif fallbacks:
            return jsonify({
                "success": True,
                "fallback_possible": True,
                "fallback_triggered": True,
                "was_fallback_promoted": False,
                "recommended_positions": fallbacks,
                "should_fetch_companies": has_preferences,
                "company_filter_ids": company_filter_ids
            }), 200

        elif no_matches:
            return jsonify({
                "success": True,
                "fallback_possible": False,
                "fallback_triggered": False,
                "was_fallback_promoted": False,
                "recommended_positions": no_matches,
                "should_fetch_companies": has_preferences,
                "company_filter_ids": company_filter_ids
            }), 200

        return jsonify({
            "success": True,
            "fallback_possible": False,
            "fallback_triggered": False,
            "was_fallback_promoted": False,
            "recommended_positions": [],
            "should_fetch_companies": has_preferences,
            "company_filter_ids": company_filter_ids
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
        industries_raw = request.args.get('preferred_industry') or request.args.get('industries', '').strip()
        company_cultures_raw = request.args.get('company_culture', '').strip()

        # ✅ If all are empty → user skipped preferences
        if not training_modes_raw and not company_sizes_raw and not industries_raw and not company_cultures_raw:
            return jsonify({
                "success": True,
                "companies": []
            }), 200

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Required position filter
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

        if company_cultures_raw:
            culture_ids = [int(x.strip()) for x in company_cultures_raw.split(',') if x.strip().isdigit()]
            if culture_ids:
                filters.append("""
                    c.id IN (
                        SELECT company_id
                        FROM company_culture
                        WHERE keyword_id IN ({})
                        GROUP BY company_id
                    )
                """.format(','.join(['%s'] * len(culture_ids))))
                params.extend(culture_ids)

        # ✅ Query to fetch company info with position_id included!
        query = f"""
            SELECT 
                DISTINCT cp.position_id,
                c.id AS company_id,
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

# 🔧 Add this helper if not defined globally
def build_in_clause(ids):
    return ','.join(['%s'] * len(ids)), tuple(ids)

def log_error(message):
    current_app.logger.error(f"❌ {message}")

@recommendation_routes.route('/user-input-summary', methods=['POST'])
def user_input_summary():
    connection = None
    try:
        data = request.get_json()
        full_name = data.get("full_name")
        gender = data.get("gender")
        major_id = data.get("major_id")
        date_of_birth = data.get("date_of_birth")
        subject_ids = data.get("subjects", [])
        technical_skill_ids = data.get("technical_skills", [])
        non_technical_skill_ids = data.get("non_technical_skills", [])
        preferences = data.get("advanced_preferences", {})

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Get Major Name
        cursor.execute("""
            SELECT name FROM prerequisites 
            WHERE id = %s AND type = 'Major'
        """, (major_id,))
        major_row = cursor.fetchone()
        major_name = major_row['name'] if major_row else None

        # ✅ Get Subjects grouped by category
        subject_names_by_cat = []
        if subject_ids:
            format_strings, subject_tuple = build_in_clause(subject_ids)
            cursor.execute(f"""
                SELECT p.id, p.name, c.id AS category_id, c.name AS category_name
                FROM prerequisites p
                JOIN categories c ON p.category_id = c.id
                WHERE p.id IN ({format_strings}) AND p.type = 'Subject'
            """, subject_tuple)
            grouped_subjects = {}
            for row in cursor.fetchall():
                cat_id = row['category_id']
                grouped_subjects.setdefault(cat_id, {
                    "category_id": cat_id,
                    "category_name": row['category_name'],
                    "subjects": []
                })["subjects"].append({
                    "id": row["id"], "name": row["name"]
                })
            subject_names_by_cat = list(grouped_subjects.values())

        # ✅ Get Technical Skills grouped by category
        tech_skills_by_cat = []
        if technical_skill_ids:
            format_strings, tech_tuple = build_in_clause(technical_skill_ids)
            cursor.execute(f"""
                SELECT p.id, p.name, c.id AS category_id, c.name AS category_name
                FROM prerequisites p
                JOIN categories c ON p.category_id = c.id
                WHERE p.id IN ({format_strings}) AND p.type = 'Technical Skill'
            """, tech_tuple)
            grouped_skills = {}
            for row in cursor.fetchall():
                cat_id = row['category_id']
                grouped_skills.setdefault(cat_id, {
                    "category_id": cat_id,
                    "category_name": row["category_name"],
                    "skills": []
                })["skills"].append({
                    "id": row["id"], "name": row["name"]
                })
            tech_skills_by_cat = list(grouped_skills.values())

        # ✅ Get Non-Technical Skills as flat list
        non_tech_names = []
        if non_technical_skill_ids:
            format_strings, nontech_tuple = build_in_clause(non_technical_skill_ids)
            cursor.execute(f"""
                SELECT name FROM prerequisites
                WHERE id IN ({format_strings}) AND type = 'Non-Technical Skill'
            """, nontech_tuple)
            non_tech_names = [row['name'] for row in cursor.fetchall()]

        # ✅ Final Ordered Response
        from collections import OrderedDict
        user_info = OrderedDict()
        user_info["full_name"] = full_name
        user_info["gender"] = gender
        user_info["date_of_birth"] = date_of_birth
        user_info["major"] = major_name
        user_info["subjects"] = subject_names_by_cat
        user_info["technical_skills"] = tech_skills_by_cat
        user_info["non_technical_skills"] = non_tech_names
        user_info["preferences"] = preferences

        # ✅ Append readable names for Advanced Preferences
        training_mode_id = preferences.get("training_mode_id") or preferences.get("training_modes", [None])[0]
        company_size_id = preferences.get("company_size_id") or preferences.get("company_sizes", [None])[0]
        industry_ids = preferences.get("preferred_industry_ids", [])  # ✅ Fixed line
        culture_ids = preferences.get("company_culture", [])

        # 🏷 Training Mode
        training_mode_name = None
        if training_mode_id:
            cursor.execute("SELECT description FROM training_modes WHERE id = %s", (training_mode_id,))
            row = cursor.fetchone()
            if row:
                training_mode_name = row["description"]

        # 🏢 Company Size
        company_size_name = None
        if company_size_id:
            cursor.execute("SELECT description FROM company_sizes WHERE id = %s", (company_size_id,))
            row = cursor.fetchone()
            if row:
                company_size_name = row["description"]

        # 🏭 Industries
        industry_names = []
        if industry_ids:
            format_str, inds = build_in_clause(industry_ids)
            cursor.execute(f"SELECT name FROM industries WHERE id IN ({format_str})", inds)
            industry_names = [row["name"] for row in cursor.fetchall()]

        # 🎯 Company Culture
        culture_names = []
        if culture_ids:
            format_str, cults = build_in_clause(culture_ids)
            cursor.execute(f"SELECT name FROM company_culture_keywords WHERE id IN ({format_str})", cults)
            culture_names = [row["name"] for row in cursor.fetchall()]

        # ✅ Safely attach translated names
        user_info["preferences"]["training_mode_name"] = training_mode_name
        user_info["preferences"]["company_size_name"] = company_size_name
        user_info["preferences"]["preferred_industry_names"] = industry_names
        user_info["preferences"]["company_culture_names"] = culture_names

        return jsonify({"success": True, "data": user_info}), 200

    except Exception as e:
        log_error(f"Error in user input summary: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@recommendation_routes.route('/fallback-prerequisites', methods=['POST'])
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

            category_key = {
                "Subject": "subjects",
                "Technical Skill": "technical_skills",
                "Non-Technical Skill": "non_technical_skills"
            }[type_]

            positions[pid][category_key].append((preq_id, weight))

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

        # ✅ Fetch names for missing prerequisites
        def build_in_clause(ids):
            return ','.join(['%s'] * len(ids)), tuple(ids)

        all_missing_ids = missing_subjects + missing_tech_skills + missing_non_tech_skills
        if not all_missing_ids:
            return jsonify({
                "success": True,
                "position_id": top_pid,
                "position_name": top_pos["position_name"],
                "missing_prerequisites": {
                    "subjects": [],
                    "technical_skills": [],
                    "non_technical_skills": []
                }
            }), 200

        format_strings, all_params = build_in_clause(all_missing_ids)
        cursor.execute(f"""
            SELECT id, name, type
            FROM prerequisites
            WHERE id IN ({format_strings})
        """, all_params)

        named_results = cursor.fetchall()

        # Organize by type
        categorized = {
            "subjects": [],
            "technical_skills": [],
            "non_technical_skills": []
        }

        for row in named_results:
            if row["type"] == "Subject":
                categorized["subjects"].append({"id": row["id"], "name": row["name"]})
            elif row["type"] == "Technical Skill":
                categorized["technical_skills"].append({"id": row["id"], "name": row["name"]})
            elif row["type"] == "Non-Technical Skill":
                categorized["non_technical_skills"].append({"id": row["id"], "name": row["name"]})

        return jsonify({
            "success": True,
            "position_id": top_pid,
            "position_name": top_pos["position_name"],
            "missing_prerequisites": categorized
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if connection and connection.is_connected():
            connection.close()

DEBUG_BYPASS_SESSION = True  # ✅ Enables access to position details without session check

@recommendation_routes.route('/api/prerequisite-names', methods=['GET'])
def get_prerequisite_names():
    try:
        type_param = request.args.get("type")
        if not type_param:
            return jsonify({"error": "Missing type parameter"}), 400

        # ✅ Map frontend value to DB value
        type_map = {
            "subject": "Subject",
            "technical": "Technical Skill",
            "non-technical": "Non-Technical Skill"
        }

        db_type = type_map.get(type_param.lower())
        if not db_type:
            return jsonify({"error": "Invalid type value."}), 400

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id AS id, name AS name
            FROM prerequisites
            WHERE type = %s
        """, (db_type,))

        data = cursor.fetchall()
        return jsonify(data), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Server failed while fetching prerequisite names", "details": str(e)}), 500

    finally:
        if connection and connection.is_connected():
            connection.close()
            
@recommendation_routes.route('/position/<int:position_id>', methods=['GET'])
def get_position_details(position_id):
    connection = None
    try:
        # ✅ Bypass session validation in dev mode
        if not DEBUG_BYPASS_SESSION:
            allowed_ids = session.get("recommended_positions")
            if allowed_ids is not None and position_id not in allowed_ids:
                current_app.logger.info(f"🚫 Access denied for position ID {position_id}")
                return jsonify({
                    "success": False,
                    "message": "Access denied. This position was not recommended."
                }), 403

        current_app.logger.info(f"📌 Fetching details for position ID {position_id}")

        # ✅ Connect to database
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # ✅ Get position details
        cursor.execute("""
            SELECT name, description, tasks, tips
            FROM positions
            WHERE id = %s
        """, (position_id,))
        position = cursor.fetchone()
        if not position:
            return jsonify({"success": False, "message": "Position not found."}), 404

        # ✅ Format tasks into list
        tasks = position["tasks"].split("\n") if position["tasks"] else []

        # ✅ Fetch prerequisites by type
        def fetch_names_by_type(prereq_type):
            cursor.execute("""
                SELECT p.name
                FROM position_prerequisites pp
                JOIN prerequisites p ON pp.prerequisite_id = p.id
                WHERE pp.position_id = %s AND p.type = %s
            """, (position_id, prereq_type))
            return [row["name"] for row in cursor.fetchall()]

        subjects = fetch_names_by_type('Subject')
        technical_skills = fetch_names_by_type('Technical Skill')
        non_technical_skills = fetch_names_by_type('Non-Technical Skill')

        # ✅ Fetch learning resources
        cursor.execute("""
            SELECT resource_type, title, url
            FROM learning_resources
            WHERE position_id = %s
        """, (position_id,))
        resources = cursor.fetchall()

        # ✅ Return structured JSON response
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
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.error(f"❌ Error: {str(e)}")
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
