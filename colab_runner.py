# -*- coding: utf-8 -*-
"""
# 🎓 AI Answer Evaluation System — Google Colab Runner

This script sets up and runs the AI-Based Answer Script Evaluation System
on Google Colab with an ngrok tunnel for public access.

## Prerequisites
- A MongoDB Atlas connection string (free tier works)
- An ngrok auth token (free at https://ngrok.com)

## Quick Start
1. Upload this file along with your project to Colab
2. Run all cells in order
3. Enter your MongoDB URI and ngrok token when prompted
4. Click the ngrok URL to access the application

Alternatively, use the Run_on_Colab.ipynb notebook.
"""

# ===========================================================================
# CELL 1: Clone or Upload Project
# ===========================================================================

import os
import subprocess

# Option A: Clone from GitHub (uncomment and edit the URL)
# !git clone https://github.com/YOUR_USERNAME/ai-answer-evaluation.git
# %cd ai-answer-evaluation

# Option B: If you uploaded a ZIP file
# !unzip -q /content/ai-answer-evaluation.zip -d /content/ai-answer-evaluation
# %cd /content/ai-answer-evaluation

# Auto-detect project directory
PROJECT_ROOT = None
for candidate in [
    "/content/ai-answer-evaluation",
    "/content/project",
    "/content/mini-project-ai-evaluation-main - final",
    "/content/mini-project-ai-evaluation-main",
]:
    if os.path.exists(os.path.join(candidate, "backend", "app.py")):
        PROJECT_ROOT = candidate
        break

if not PROJECT_ROOT:
    # Check if we're already in the project dir
    if os.path.exists("backend/app.py"):
        PROJECT_ROOT = os.getcwd()
    else:
        print("❌ Project directory not found!")
        print("   Please either:")
        print("   1. Clone from GitHub: !git clone <your-repo-url>")
        print("   2. Upload and unzip your project files")
        print("   Then re-run this cell.")

if PROJECT_ROOT:
    os.chdir(PROJECT_ROOT)
    print(f"✅ Project directory: {PROJECT_ROOT}")
    print(f"   Contents: {os.listdir('.')}")


# ===========================================================================
# CELL 2: Install Dependencies
# ===========================================================================

print("📦 Installing dependencies...")
subprocess.run(
    ["pip", "install", "-q", "-r", "backend/requirements.txt"],
    check=True
)

# pyngrok is already in requirements.txt, but ensure it's installed
subprocess.run(["pip", "install", "-q", "pyngrok"], check=True)

# Download NLTK data
print("📚 Downloading NLTK data...")
import nltk
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('wordnet', quiet=True)

print("✅ All dependencies installed!")


# ===========================================================================
# CELL 3: Configure Environment
# ===========================================================================

import secrets
from getpass import getpass

print("=" * 60)
print("  🔧 Configuration Setup")
print("=" * 60)

# MongoDB
print("\n📊 MongoDB Configuration")
print("   Get a free cluster at: https://www.mongodb.com/atlas")
print("   Connection string format: mongodb+srv://user:pass@cluster.mongodb.net/")
MONGO_URI = getpass("Enter your MongoDB URI: ")

mongo_db_name = input("Enter database name (default: NewAIEval): ").strip()
MONGO_DB_NAME = mongo_db_name if mongo_db_name else "NewAIEval"

# ngrok
print("\n🌐 ngrok Configuration")
print("   Get a free token at: https://dashboard.ngrok.com/get-started/your-authtoken")
NGROK_TOKEN = getpass("Enter your ngrok auth token: ")

# Generate a secure JWT secret
JWT_SECRET = secrets.token_hex(32)

# Write .env file
env_content = f"""# Auto-generated for Google Colab
MONGO_URI={MONGO_URI}
MONGO_DB_NAME={MONGO_DB_NAME}
JWT_SECRET_KEY={JWT_SECRET}
JWT_ACCESS_TOKEN_EXPIRES=86400
FLASK_DEBUG=0
MAX_CONTENT_LENGTH=8388608
MAX_CONCURRENT_EVALUATIONS=1
MAX_PDF_PAGES=10
MAX_EXTRACTED_CHARS=20000
OLLAMA_ENABLED=0
NGROK_AUTH_TOKEN={NGROK_TOKEN}
"""

with open(".env", "w") as f:
    f.write(env_content)

print(f"\n✅ Configuration saved!")
print(f"   Database: {MONGO_DB_NAME}")
print(f"   JWT Secret: {JWT_SECRET[:8]}...{JWT_SECRET[-8:]}")


# ===========================================================================
# CELL 4: Seed Admin User
# ===========================================================================

print("👤 Creating admin user...")
os.chdir(os.path.join(PROJECT_ROOT, "backend"))

# Run seed script
result = subprocess.run(
    ["python", "seed.py"],
    capture_output=True, text=True,
    cwd=os.path.join(PROJECT_ROOT, "backend")
)

print(result.stdout)
if result.stderr:
    print(f"⚠️ {result.stderr}")

os.chdir(PROJECT_ROOT)

print("\n📋 Default admin credentials:")
print("   Email:    admin@system.com")
print("   Password: admin123")
print("   ⚠️ Change the password after first login!")


# ===========================================================================
# CELL 5: Start the Application with ngrok
# ===========================================================================

import sys
import threading
import time
import urllib.request
import json

from pyngrok import ngrok

# Add backend to Python path
backend_path = os.path.join(PROJECT_ROOT, "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Setup ngrok
ngrok.set_auth_token(NGROK_TOKEN)

# Start Flask in a background thread
def run_flask():
    """Run Flask app in background."""
    os.chdir(backend_path)
    os.environ["FLASK_DEBUG"] = "0"
    from app import app
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# Wait for Flask to start
print("⏳ Starting Flask server...")
for attempt in range(15):
    time.sleep(2)
    try:
        response = urllib.request.urlopen("http://localhost:5000/api/health")
        health = json.loads(response.read().decode())
        print(f"✅ Flask server is running! (Memory: {health.get('memory_mb', '?')}MB)")
        break
    except Exception:
        if attempt < 14:
            print(f"   Waiting... ({(attempt + 1) * 2}s)")
        else:
            print("⚠️ Server may still be starting, proceeding anyway...")

# Create ngrok tunnel
public_url = ngrok.connect(5000, "http")
tunnel_url = public_url.public_url

print()
print("=" * 60)
print("  🎉 APPLICATION IS LIVE!")
print("=" * 60)
print(f"\n  🌐 Public URL: {tunnel_url}")
print(f"  📊 Health:     {tunnel_url}/api/health")
print(f"\n  📋 Login Credentials:")
print(f"     Admin:   admin@system.com / admin123")
print(f"\n  ⚠️ Keep this notebook running to maintain the server.")
print(f"  ⚠️ The URL will change each time you restart.")
print("=" * 60)


# ===========================================================================
# CELL 6: Monitor & Logs (optional — run when needed)
# ===========================================================================

# Uncomment to check health status:
# import requests
# r = requests.get(f"{public_url}/api/health")
# print(r.json())

# Uncomment to stop the tunnel:
# ngrok.disconnect(public_url)
# print("🛑 Tunnel disconnected")
