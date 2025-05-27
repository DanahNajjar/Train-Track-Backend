from flask import Flask, send_from_directory
from flask_cors import CORS
import os
import logging
from dotenv import load_dotenv

# ✅ Load environment (.env.local for dev, .env.remote for prod)
if os.getenv("FLASK_ENV") == "production":
    load_dotenv(dotenv_path=".env.remote")
    logging.info("🔧 Loaded .env.remote for production")
else:
    load_dotenv(dotenv_path=".env.local")
    logging.info("🔧 Loaded .env.local for development")

# ✅ Setup Logging
logging.basicConfig(level=logging.INFO)

# ✅ Create Flask App
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "train_track_secret_key")

# ✅ Enable CORS — allow frontend to call backend
CORS(app, supports_credentials=True, resources={
    r"/*": {
        "origins": [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "https://train-track-frontend.onrender.com"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"]
    }
})

# ✅ Register Blueprints
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

# ✅ Local static file serving (for dev only)
if os.getenv("FLASK_ENV") != "production":
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        return send_from_directory(app.static_folder, filename)

# ✅ Run App
if __name__ == '__main__':
    app.run(debug=True)
