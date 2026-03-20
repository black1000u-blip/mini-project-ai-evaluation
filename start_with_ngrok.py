"""
🚀 AI Evaluation System Launcher — Minimalist version
"""
import os
import sys
import time
import threading
import urllib.request
import logging
import subprocess

# 1. Load environment and suppress logging
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Set environment for silent startup in backend
os.environ['SILENT_STARTUP'] = '1'

# Suppress external logging
logging.getLogger('pyngrok').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

NGROK_AUTH_TOKEN = os.getenv('NGROK_AUTH_TOKEN', '')
FLASK_PORT = int(os.getenv('PORT', 5000))

# 2. Check dependencies (Silent)
def ensure_dependencies():
    required = ["pyngrok", "flask-cors", "flask-jwt-extended", "pymongo", "bcrypt", "rapidfuzz"]
    for lib in required:
        try:
            mod_name = lib.replace("-", "_")
            if lib == "PyMuPDF": mod_name = "fitz"
            __import__(mod_name)
        except ImportError:
            print(f"📦 Installing missing dependency: {lib}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", lib])

# Start dependency check
ensure_dependencies()
from pyngrok import ngrok

# 3. Flask Runner
def start_flask():
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    os.chdir(backend_dir)
    os.environ['FLASK_DEBUG'] = '0'
    
    try:
        from app import app
        # Only print once we know it's starting
        app.run(host='0.0.0.0', port=FLASK_PORT, debug=False, use_reloader=False)
    except Exception as e:
        print(f"\n❌ SERVER CRASHED: {e}")

# Start Flask
print(f"⏳ Starting Flask server on port {FLASK_PORT} ...")
flask_thread = threading.Thread(target=start_flask, daemon=True)
flask_thread.start()

# 4. Wait for server (Silent)
server_ready = False
for attempt in range(15):
    time.sleep(1)
    try:
        response = urllib.request.urlopen(f'http://localhost:{FLASK_PORT}/api/health', timeout=2)
        if response.status == 200:
            server_ready = True
            break
    except Exception:
        pass

# 5. Connect ngrok
if NGROK_AUTH_TOKEN:
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    try:
        public_url = ngrok.connect(FLASK_PORT, "http")
        tunnel_url = public_url.public_url

        print(f"  🌐 Public URL:  {tunnel_url}")
        print(f"  📊 Health:      {tunnel_url}/api/health")
        print(f"  🏠 Local:       http://localhost:{FLASK_PORT}")
        print(f"\n  📋 Default Admin Login:")
        print(f"     Email:     admin@system.com | Password: admin123\n")

        while True: time.sleep(1)
    except Exception as e:
        print(f"\n❌ ngrok failed: {e}")
        print(f"  🏠 Local only: http://localhost:{FLASK_PORT}")
        while True: time.sleep(1)
else:
    print(f"\n❌ NGROK_AUTH_TOKEN not found in .env.")
    print(f"  🏠 Local only: http://localhost:{FLASK_PORT}")
    while True: time.sleep(1)
