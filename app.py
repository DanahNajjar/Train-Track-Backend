from flask import Flask, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Import blueprints
from api.wizard_routes import wizard_routes
from api.recommendation import recommendation_routes

app = Flask(__name__, static_folder='static')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "train_track_secret_key")
CORS(app)

# ✅ register wizard routes with /wizard prefix
app.register_blueprint(wizard_routes, url_prefix='/wizard')
app.register_blueprint(recommendation_routes)

@app.route('/')
def home():
    return "✅ Train Track Backend is Running!"

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == '__main__':
    app.run(debug=True)
    
@app.route('/test')
def test():
    return "✅ /test route is working!"


