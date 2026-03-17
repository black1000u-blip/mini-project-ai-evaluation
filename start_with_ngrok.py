"""
🚀 Start the AI Evaluation System with ngrok Tunnel

This script starts the Flask backend server and creates an ngrok tunnel
so the application can be accessed publicly from anywhere.

Usage:
    python start_with_ngrok.py

Environment:
    Set NGROK_AUTH_TOKEN in your .env file (or pass as env variable).
    Get your free token at: https://dashboard.ngrok.com/get-started/your-authtoken
"""

import os
import sys
import time
import threading
import urllib.request
import json

# ---------------------------------------------------------------------------
# 1. Load environment variables
# ---------------------------------------------------------------------------
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

NGROK_AUTH_TOKEN = os.getenv('NGROK_AUTH_TOKEN', '')
FLASK_PORT = int(os.getenv('PORT', 5000))

if not NGROK_AUTH_TOKEN:
    print("❌ NGROK_AUTH_TOKEN not found!")
    print("   Set it in your .env file or as an environment variable.")
    print("   Get your free token at: https://dashboard.ngrok.com/get-started/your-authtoken")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 2. Install pyngrok if needed
# ---------------------------------------------------------------------------
try:
    from pyngrok import ngrok, conf
except ImportError:
    print("📦 Installing pyngrok...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pyngrok"])
    from pyngrok import ngrok, conf

# ---------------------------------------------------------------------------
# 3. Start Flask in a background thread
# ---------------------------------------------------------------------------

def start_flask():
    """Run the Flask application."""
    # Add backend directory to Python path
    backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    os.chdir(backend_dir)
    os.environ['FLASK_DEBUG'] = '0'

    from app import app
    app.run(host='0.0.0.0', port=FLASK_PORT, debug=False, use_reloader=False)


print("=" * 60)
print("  🎓 AI-Based Answer Script Evaluation System")
print("  Starting with ngrok tunnel...")
print("=" * 60)

# Start Flask
flask_thread = threading.Thread(target=start_flask, daemon=True)
flask_thread.start()

# Wait for Flask to be ready
print("\n⏳ Starting Flask server on port", FLASK_PORT, "...")
server_ready = False

for attempt in range(15):
    time.sleep(2)
    try:
        response = urllib.request.urlopen(f'http://localhost:{FLASK_PORT}/api/health')
        health_data = json.loads(response.read().decode())
        print(f"✅ Flask server is running! (Memory: {health_data.get('memory_mb', '?')}MB)")
        server_ready = True
        break
    except Exception:
        dots = "." * (attempt + 1)
        print(f"   Waiting{dots} ({(attempt + 1) * 2}s)")

if not server_ready:
    print("⚠️  Server may still be starting, attempting ngrok anyway...")

# ---------------------------------------------------------------------------
# 4. Start ngrok tunnel
# ---------------------------------------------------------------------------
print("\n🌐 Creating ngrok tunnel...")

# Configure ngrok
ngrok.set_auth_token(NGROK_AUTH_TOKEN)

try:
    # Open tunnel
    public_url = ngrok.connect(FLASK_PORT, "http")
    tunnel_url = public_url.public_url

    print("\n" + "=" * 60)
    print("  🎉 APPLICATION IS LIVE!")
    print("=" * 60)
    print(f"\n  🌐 Public URL:  {tunnel_url}")
    print(f"  📊 Health:      {tunnel_url}/api/health")
    print(f"  🏠 Local:       http://localhost:{FLASK_PORT}")
    print(f"\n  📋 Default Admin Login:")
    print(f"     Email:     admin@system.com")
    print(f"     Password:  admin123")
    print(f"\n  ⚠️  Press Ctrl+C to stop the server and tunnel.")
    print("=" * 60)

    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        ngrok.disconnect(public_url)
        ngrok.kill()
        print("✅ ngrok tunnel closed.")
        print("✅ Server stopped.")

except Exception as e:
    print(f"\n❌ Failed to create ngrok tunnel: {e}")
    print(f"   The server is still running locally at: http://localhost:{FLASK_PORT}")
    print(f"\n   Common issues:")
    print(f"   - Invalid auth token → check NGROK_AUTH_TOKEN in .env")
    print(f"   - Token expired → get a new one at https://dashboard.ngrok.com")
    print(f"\n   Press Ctrl+C to stop the server.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped.")
