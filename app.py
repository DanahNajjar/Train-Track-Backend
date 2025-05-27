from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging

# ✅ Load correct environment
if os.getenv("FLASK_ENV") == "production":
    load_dotenv(".env.remote")
    logging.info("🔧 Loaded .env.remote for production")
else:
    load_dotenv(".env.local")
    logging.info("🔧 Loaded .env.local for development")

# ✅ Logging
logging.basicConfig(level=logging.INFO)

# ✅ Create Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "train_track_secret_key")

# ✅ FRONTEND Origins
FRONTEND_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://train-track-frontend.onrender.com",
    "https://accounts.google.com"
]

# ✅ Enable CORS (full support including preflight OPTIONS)
CORS(app,
     resources={r"/*": {"origins": FRONTEND_ORIGINS}},
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# ✅ Register Blueprints
from api.user_routes import user_routes
from api.wizard_routes import wizard_routes
from api.recommendation import recommendation_routes

app.register_blueprint(user_routes, url_prefix="/user")
app.register_blueprint(wizard_routes, url_prefix="/wizard")
app.register_blueprint(recommendation_routes)

# ✅ Health check
@app.route("/")
def home():
    return "✅ Train Track Backend is Running!"

@app.route("/test")
def test():
    return "✅ /test route is working!"

# ✅ Serve static files in dev only
if os.getenv("FLASK_ENV") != "production":
    @app.route("/static/<path:filename>")
    def serve_static(filename):
        return send_from_directory(app.static_folder, filename)

# ✅ Run
if __name__ == "__main__":
    app.run(debug=True)
