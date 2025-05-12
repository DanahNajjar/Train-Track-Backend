from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging

# ✅ Setup Logging
logging.basicConfig(level=logging.INFO)

# ✅ Determine and load the correct environment file
env_file = ".env.remote" if os.getenv("FLASK_ENV") == "production" else ".env.local"
load_dotenv(dotenv_path=env_file)
logging.info(f"🔧 Loaded environment from: {env_file}")

# ✅ Import routes
from api.wizard_routes import wizard_routes
from api.recommendation import recommendation_routes

# ✅ Create Flask App
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "train_track_secret_key")

# ✅ Enable CORS for both 127.0.0.1 and localhost on port 8000
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)


# ✅ Register blueprints
app.register_blueprint(wizard_routes, url_prefix='/wizard')
app.register_blueprint(recommendation_routes)

# ✅ Health Check Route
@app.route('/')
def home():
    return "✅ Train Track Backend is Running!"

# ✅ Serve static images like subject category icons
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

# ✅ Optional test route
@app.route('/test')
def test():
    return "✅ /test route is working!"
    
@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")  # or "http://localhost:8000"
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    return response

# ✅ Run the app
if __name__ == '__main__':
    app.run(debug=True)
