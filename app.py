# app.py

from flask import Flask, send_from_directory
from flask_cors import CORS

# Import blueprints
from api.wizard_routes import wizard_routes
from api.recommendation import recommendation_routes

app = Flask(__name__)
app.secret_key = 'train_track_secret_key'  # Required for session management
CORS(app)

# Register blueprint routes
app.register_blueprint(wizard_routes)
app.register_blueprint(recommendation_routes)

# Root route for testing
@app.route('/')
def home():
    return "Train Track Backend is Running!"

# Serve static files
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)
