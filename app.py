# app.py
from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Import blueprints
from api.wizard_routes import wizard_routes
from api.recommendation import recommendation_routes

# Initialize Flask app
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "train_track_secret_key")
CORS(app)

# ✅ Register all route blueprints with proper prefix
app.register_blueprint(wizard_routes, url_prefix="/wizard")
app.register_blueprint(recommendation_routes)

# Health check endpoint
@app.route('/')
def home():
    return "✅ Train Track Backend is Running!"

# Serve static files (CSS, JS, images)
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

# Entry point
if __name__ == '__main__':
    app.run(debug=True)
