import os
import sys
from dotenv import load_dotenv
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Load environment variables
load_dotenv()

from flask import Flask, send_from_directory
from flask_cors import CORS
from src.database import db
# Import models after db is defined to avoid circular imports
from src.routes.user import user_bp
from src.routes.project import project_bp
from src.routes.task import task_bp
from src.routes.video_generation import video_bp
from src.routes.auth import auth_bp
from src.routes.api_keys import api_keys_bp
from src.routes.voice_cloning import voice_cloning_bp
from src.routes.presets import presets_bp
from src.routes.templates import templates_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

# Enable CORS for all routes
CORS(app, resources={
    r"/api/*": {"origins": [os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173')]},
    r"/final/*": {"origins": [os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173')]}
})

# Database configuration
# Explicitly set the database path to avoid Flask's default instance folder behavior
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'database', 'app.db'))
# Ensure the database directory exists BEFORE initializing the database
db_dir = os.path.dirname(db_path)
os.makedirs(db_dir, exist_ok=True)
# Ensure the database directory has write permissions
os.chmod(db_dir, 0o777)

# If database file exists, ensure it has write permissions
if os.path.exists(db_path):
    os.chmod(db_path, 0o666)  # Read/write for owner, group, and others
else:
    # Create an empty database file with proper permissions
    with open(db_path, 'w') as f:
        pass
    os.chmod(db_path, 0o666)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', f"sqlite:///{db_path}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    # Import models here to ensure they're registered with SQLAlchemy
    from src.models.user import User
    from src.models.project import Project
    from src.models.task import Task
    from src.models.media_asset import MediaAsset
    from src.models.api_key import ApiKey
    from src.models.preset import FormatPreset
    from src.models.template import VideoTemplate
    
    # Create tables
    db.create_all()
    
    # Seed default format presets
    SEED_PRESETS = [
        ('YouTube Landscape', 'youtube', 1920, 1080, 30, 60, 600, True),
        ('YouTube Shorts', 'shorts', 1080, 1920, 30, 15, 60, False),
        ('TikTok', 'tiktok', 1080, 1920, 30, 15, 60, False),
        ('Instagram Reels', 'reels', 1080, 1920, 30, 15, 60, False),
        ('Instagram Square', 'instagram', 1080, 1080, 30, 15, 60, False),
        ('Twitter/X', 'twitter', 1280, 720, 30, 15, 60, False),
    ]
    if FormatPreset.query.count() == 0:
        for name, platform, w, h, fps, dmin, dmax, is_def in SEED_PRESETS:
            db.session.add(FormatPreset(name=name, platform=platform, width=w, height=h,
                                        fps=fps, duration_min=dmin, duration_max=dmax, is_default=is_def))
        db.session.commit()
    
    # Debug: Print out what tables were created
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"Database tables created: {tables}")

# Register blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(project_bp, url_prefix='/api')
app.register_blueprint(task_bp, url_prefix='/api')
app.register_blueprint(video_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(api_keys_bp, url_prefix='/api')
app.register_blueprint(voice_cloning_bp, url_prefix='/api')
app.register_blueprint(presets_bp, url_prefix='/api')
app.register_blueprint(templates_bp, url_prefix='/api')

# Serve static files
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

# Serve final videos
@app.route('/final/<path:filename>')
def serve_final_video(filename):
    # Use consolidated directory at the project root level
    final_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'final')
    file_path = os.path.join(final_dir, filename)
    if os.path.exists(file_path):
        response = send_from_directory(final_dir, filename)
        response.headers['Content-Type'] = 'video/mp4'
        response.headers['Accept-Ranges'] = 'bytes'
        return response
    else:
        return "Video not found", 404

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5004))
    app.run(host='0.0.0.0', port=port, debug=True)
