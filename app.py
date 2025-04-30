from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging

# ✅ Setup Logging
logging.basicConfig(level=logging.INFO)

# ✅ Determine and load the correct environment file
env_file = ".env.remote" if os.getenv("FLASK_ENV") == "production" else ".env.local"
# ✅ Automatically load correct environment file based on FLASK_ENV
env_file = ".env.remote" if os.getenv("FLASK_ENV") == "production" else ".env.local"
load_dotenv(dotenv_path=env_file)
logging.info(f"🔧 Loaded environment from: {env_file}")

# ✅ Import routes
from api.wizard_routes import wizard_routes
from api.recommendation import recommendation_routes

# ✅ Create app
app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "train_track_secret_key")
CORS(app)

# ✅ Register routes
app.register_blueprint(wizard_routes, url_prefix='/wizard')
app.register_blueprint(recommendation_routes)

# ✅ Default route
@app.route('/')
def home():
    return "✅ Train Track Backend is Running!"

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/test')
def test():
    return "✅ /test route is working!"

# ✅ Run app
if __name__ == '__main__':
    app.run(debug=True)
