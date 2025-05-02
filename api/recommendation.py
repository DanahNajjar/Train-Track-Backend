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

            # ✅ Determine fit level based on actual match score
            fit_level = get_fit_level(matched_weight, base)

            if fit_level in ["No Match", "Fallback Only"]:
                continue

            # ✅ Log internal scoring for debugging
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
                "non_technical_skill_fit_percentage": round((matched["non_technical_skills"] / total["non_technical_skills"]) * 100, 2) if total["non_technical_skills"] else 0
            })

        results.sort(key=lambda x: x['match_score_percentage'], reverse=True)

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

        # ✅ NEW: If all are empty → user skipped preferences
        if not training_modes_raw and not company_sizes_raw and not industries_raw:
            return jsonify({
                "success": True,
                "positions": []  # Return empty result if no preferences selected
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

        # ✅ Build and execute query
        query = f"""
            SELECT 
                c.id AS company_id,
                c.company_name,
                cs.description AS company_size,
                i.name AS industry,
                tm.description AS training_mode,
                b.city AS location,
                b.address,
                b.website_link,
                p.id AS position_id,
                p.name AS position_name
            FROM companies c
            JOIN company_positions cp ON c.id = cp.company_id
            JOIN positions p ON cp.position_id = p.id
            JOIN company_sizes cs ON c.company_sizes_id = cs.id
            JOIN industries i ON c.industry_id = i.id
            JOIN training_modes tm ON c.training_mode_id = tm.id
            JOIN branches b ON c.id = b.company_id AND b.is_main_branch = 1
            WHERE {" AND ".join(filters)}
        """

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        # ✅ Group companies by position
        grouped = {}
        for row in rows:
            pos_id = row['position_id']
            if pos_id not in grouped:
                grouped[pos_id] = {
                    "position_id": pos_id,
                    "position_name": row['position_name'],
                    "companies": []
                }

            grouped[pos_id]['companies'].append({
                "company_id": row['company_id'],
                "company_name": row['company_name'],
                "company_size": row['company_size'],
                "industry": row['industry'],
                "training_mode": row['training_mode"],
                "location": row['location'],
                "address": row['address'],
                "website_link": row['website_link']
            })

        return jsonify({
            "success": True,
            "positions": list(grouped.values())
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        current_app.logger.error(f"❌ Error fetching companies for positions: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()
