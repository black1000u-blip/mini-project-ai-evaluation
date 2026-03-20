import gc
import os
import sys
import threading
from datetime import timedelta
import certifi
import logging

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from pymongo import MongoClient

from config import Config

# ---------------------------------------------------------------------------
# Memory Management for Render Free Tier (512MB)
# ---------------------------------------------------------------------------

def get_memory_usage_mb():
    """Get current memory usage in MB (cross-platform)."""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return -1  # psutil not available


def force_gc():
    """Force garbage collection to free memory."""
    gc.collect()


# Semaphore to limit concurrent evaluations
evaluation_semaphore = threading.Semaphore(Config.MAX_CONCURRENT_EVALUATIONS)

# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------

# Configure logging
if os.getenv('SILENT_STARTUP') == '1':
    logging.basicConfig(level=logging.WARNING, format='%(message)s')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("="*60)
    logging.info("  AI-Based Answer Script Evaluation System")
    logging.info("  Optimized for Render Free Tier (512MB RAM)")
    logging.info("="*60)
    Config.log_config()

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend'),
    static_url_path=''
)

# Configuration
app.config['JWT_SECRET_KEY'] = Config.JWT_SECRET_KEY
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(seconds=Config.JWT_ACCESS_TOKEN_EXPIRES)
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
app.config['PROPAGATE_EXCEPTIONS'] = True

# Extensions
CORS(app)
jwt = JWTManager(app)

# ---------------------------------------------------------------------------
# Database (with connection pooling optimized for low memory)
# ---------------------------------------------------------------------------

# Universal connection logic: Only use TLS if not on localhost
mongo_kwargs = {
    'maxPoolSize': 5,
    'minPoolSize': 1,
    'maxIdleTimeMS': 30000,
    'serverSelectionTimeoutMS': 5000,
    'connectTimeoutMS': 5000,
}

# Only apply the certificate file if we're not connecting to localhost
if "localhost" not in Config.MONGO_URI and "127.0.0.1" not in Config.MONGO_URI:
    mongo_kwargs['tlsCAFile'] = certifi.where()

mongo_client = MongoClient(Config.MONGO_URI, **mongo_kwargs)
db = mongo_client[Config.MONGO_DB_NAME]

# Create indexes for performance
try:
    db['users'].create_index('email', unique=True)
    db['submissions'].create_index('student_id')
    db['submissions'].create_index('assignment_id')
    db['submissions'].create_index('status')
    db['assignments'].create_index('faculty_id')
    logging.info("[DB] Indexes ensured on users, submissions, assignments")
except Exception as e:
    logging.warning(f"[DB] Index creation warning: {e}")

# Ensure upload directory exists
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

# ---------------------------------------------------------------------------
# Register Blueprints
# ---------------------------------------------------------------------------

from routes.auth import auth_bp
from routes.student import student_bp
from routes.faculty import faculty_bp
from routes.admin import admin_bp

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(student_bp, url_prefix='/api/student')
app.register_blueprint(faculty_bp, url_prefix='/api/faculty')
app.register_blueprint(admin_bp, url_prefix='/api/admin')

# ---------------------------------------------------------------------------
# Serve Frontend
# ---------------------------------------------------------------------------

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/health')
def health_check():
    """Health check endpoint for Render."""
    memory_mb = get_memory_usage_mb()
    status = {
        'status': 'healthy',
        'memory_mb': round(memory_mb, 1) if memory_mb > 0 else 'unknown',
        'memory_limit_mb': 512,
        'concurrent_eval_limit': Config.MAX_CONCURRENT_EVALUATIONS,
    }
    
    # Warn if memory is high
    if memory_mb > 400:
        status['warning'] = 'High memory usage'
        force_gc()  # Try to free memory
    
    return jsonify(status), 200


@app.route('/api/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded files (PDFs, images)."""
    return send_from_directory(Config.UPLOAD_FOLDER, filename)


@app.route('/<path:path>')
def serve_frontend(path):
    """Serve frontend files; fall back to index.html for SPA-style routing."""
    file_path = os.path.join(app.static_folder, path)
    if os.path.isfile(file_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------

@app.errorhandler(400)
def bad_request(e):
    return {'error': 'Bad request', 'message': str(e)}, 400


@app.errorhandler(401)
def unauthorized(e):
    return {'error': 'Unauthorized', 'message': 'Authentication required'}, 401


@app.errorhandler(403)
def forbidden(e):
    return {'error': 'Forbidden', 'message': 'You do not have permission'}, 403


@app.errorhandler(404)
def not_found(e):
    return {'error': 'Not found', 'message': 'Resource not found'}, 404


@app.errorhandler(413)
def file_too_large(e):
    return {'error': 'File too large', 'message': f'Maximum file size is {Config.MAX_CONTENT_LENGTH // (1024 * 1024)}MB'}, 413


@app.errorhandler(500)
def server_error(e):
    return {'error': 'Internal server error', 'message': 'Something went wrong'}, 500

# ---------------------------------------------------------------------------
# Auto-evaluate pending/stuck submissions on startup
# ---------------------------------------------------------------------------

def _retry_pending_submissions():
    """
    Find all pending/stuck submissions and mark them for retry.
    
    Note: In production on Render, we don't auto-trigger evaluations on startup
    to prevent memory spikes. Instead, we just reset stuck submissions to pending
    and let users manually retry.
    """
    from models.submission import SubmissionModel

    submission_model = SubmissionModel(db)

    # Reset any stuck 'processing' to 'pending'
    stuck = db['submissions'].update_many(
        {'status': 'processing'},
        {'$set': {'status': 'pending', 'progress': 0, 'progress_step': 'Ready for retry'}}
    )
    if stuck.modified_count:
        logging.warning(f"[STARTUP] Reset {stuck.modified_count} stuck submission(s) to pending.")

    # Count pending (don't auto-trigger to save memory)
    pending_count = db['submissions'].count_documents({'status': 'pending'})
    if pending_count:
        logging.info(f"[STARTUP] {pending_count} pending submission(s) waiting for evaluation.")
        logging.info(f"[STARTUP] Students can use the retry button to process them.")
    
    # Force garbage collection after startup
    force_gc()
    logging.info(f"[STARTUP] Memory usage: {get_memory_usage_mb():.1f}MB")


# Only run startup tasks if this is the main process (not gunicorn worker fork)
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not Config.DEBUG:
    with app.app_context():
        _retry_pending_submissions()

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    logging.info("=" * 60)
    logging.info("  AI-Based Answer Script Evaluation System")
    logging.info("  Running at http://localhost:5000")
    logging.info("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=Config.DEBUG)
