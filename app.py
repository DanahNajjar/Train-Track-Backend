from flask import Flask, send_from_directory
from flask_cors import CORS
import os
import logging

# ✅ Setup Logging
logging.basicConfig(level=logging.INFO)

# ✅ Load environment variables
from dotenv import load_dotenv
env_file = ".env.remote" if os.getenv("FLASK_ENV") == "production" else ".env.local"
load_dotenv(dotenv_path=env_file)
logging.info(f"🔧 Loaded {env_file} for {'production' if 'remote' in env_file else 'development'}")

# ✅ Create Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "train_track_secret_key")

# ✅ Allowed Frontend Origins
FRONTEND_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://train-track-frontend.onrender.com"
]

# ✅ Enable CORS for all necessary routes
CORS(app, resources={
    r"/wizard/*": {"origins": FRONTEND_ORIGINS},
    r"/position/*": {"origins": FRONTEND_ORIGINS},
    r"/recommendations*": {"origins": FRONTEND_ORIGINS},
    r"/api/prerequisite-names": {"origins": FRONTEND_ORIGINS},
    r"/companies-for-positions": {"origins": FRONTEND_ORIGINS},
    r"/user-input-summary": {"origins": FRONTEND_ORIGINS}
}, supports_credentials=True)

# ✅ Import and register blueprints
from api.wizard_routes import wizard_routes
from api.recommendation import recommendation_routes
from api.user_routes import user_routes

app.register_blueprint(wizard_routes, url_prefix='/wizard')
app.register_blueprint(recommendation_routes)  # ✅ includes /recommendations and fallback
app.register_blueprint(user_routes, url_prefix='/user')

# ✅ Root health check
@app.route('/')
def home():
    return "✅ Train Track Backend is Running!"

@app.route('/test')
def test():
    return "✅ /test route is working!"

# ✅ Serve static assets locally
if os.getenv("FLASK_ENV") != "production":
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        return send_from_directory(app.static_folder, filename)

# ✅ Start local server
if __name__ == '__main__':
    app.run(debug=True)
