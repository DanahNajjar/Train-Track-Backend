from flask import Flask, send_from_directory
from flask_cors import CORS
from api.recommendation import get_fallback_prerequisites
import os
import logging

# ✅ Setup Logging
logging.basicConfig(level=logging.INFO)

# ✅ Load environment variables
if os.getenv("FLASK_ENV") == "production":
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=".env.remote")
    logging.info("🔧 Loaded .env.remote for production")
else:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=".env.local")
    logging.info("🔧 Loaded .env.local for development")

# ✅ Create Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "train_track_secret_key")

# ✅ Frontend origins (local + deployed)
FRONTEND_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://train-track-frontend.onrender.com"
]

CORS(app, resources={
    r"/wizard/*": {"origins": FRONTEND_ORIGINS},
    r"/position/*": {"origins": FRONTEND_ORIGINS},
    r"/recommendations/*": {"origins": FRONTEND_ORIGINS},  # ✅ This already includes /recommendations/fallback-prerequisites
    r"/api/prerequisite-names": {"origins": FRONTEND_ORIGINS},
    r"/companies-for-positions": {"origins": FRONTEND_ORIGINS},
    r"/user-input-summary": {"origins": FRONTEND_ORIGINS},
    r"/fallback-prerequisites": {"origins": FRONTEND_ORIGINS}  # ✅ Optional — keep if this route also exists outside /recommendations/
}, supports_credentials=True)

# ✅ Register blueprints
from api.wizard_routes import wizard_routes
from api.recommendation import recommendation_routes
from api.user_routes import user_routes

app.register_blueprint(wizard_routes, url_prefix='/wizard')
app.register_blueprint(recommendation_routes)
app.register_blueprint(user_routes, url_prefix='/user')

# ✅ Health Check
@app.route('/')
def home():
    return "✅ Train Track Backend is Running!"

@app.route('/test')
def test():
    return "✅ /test route is working!"

# ✅ Local static file serving (not for production)
if os.getenv("FLASK_ENV") != "production":
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        return send_from_directory(app.static_folder, filename)

# ✅ Run app
if __name__ == '__main__':
    app.run(debug=True)
