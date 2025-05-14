from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging

# ✅ Setup Logging
logging.basicConfig(level=logging.INFO)

# ✅ Load environment variables
env_file = ".env.remote" if os.getenv("FLASK_ENV") == "production" else ".env.local"
load_dotenv(dotenv_path=env_file)
logging.info(f"🔧 Loaded environment from: {env_file}")

# ✅ Create Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "train_track_secret_key")

# ✅ Enable CORS — for local + deployed frontend
CORS(app, resources={
    r"/wizard/*": {
        "origins": [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "https://train-track-frontend.onrender.com"
        ]
    },
    r"/position/*": {
        "origins": [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "https://train-track-frontend.onrender.com"
        ]
    },
    r"/recommendations*": {
        "origins": [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "https://train-track-frontend.onrender.com"
        ]
    },
    r"/companies-for-positions": {
        "origins": [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "https://train-track-frontend.onrender.com"
        ]
    }
}, supports_credentials=True)

# ✅ Import & register blueprints
from api.wizard_routes import wizard_routes
from api.recommendation import recommendation_routes

app.register_blueprint(wizard_routes, url_prefix='/wizard')
app.register_blueprint(recommendation_routes)

# ✅ Static & health check routes
@app.route('/')
def home():
    return "✅ Train Track Backend is Running!"

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/test')
def test():
    return "✅ /test route is working!"

# ✅ Run server
if __name__ == '__main__':
    app.run(debug=True)
