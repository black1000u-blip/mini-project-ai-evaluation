# 🚀 FINAL STABLE STARTER (Persists Uploads + Removes Warnings)
import os

repo_url = "https://github.com/black1000u-blip/mini-project-ai-evaluation.git"
project_folder = "mini-project-ai-evaluation"

# --- 1. SMART SYNC (Keeps your 'uploads' folder safe) ---
%cd /content
if os.path.exists(project_folder):
    print("✅ Project exists. Updating code (Keeping your uploads safe!)...")
    %cd {project_folder}
    !git reset --hard HEAD
    !git pull
else:
    print("First time setup. Cloning repository...")
    !git clone -q {repo_url}
    %cd {project_folder}

# --- 2. INSTALL DEPENDENCIES ---
!pip install -q pyngrok python-dotenv flask-cors flask-jwt-extended pymongo bcrypt rapidfuzz google-generativeai pymupdf pillow

# --- 3. PATCH FRONTEND ---
print("🛠️ Patching Frontend layers...")
auth_js = "frontend/js/auth.js"
with open(auth_js, "r") as f: content = f.read()
if "ngrok-skip-browser-warning" not in content:
    content = content.replace("const headers = options.headers || {};", "const headers = options.headers || {}; headers['ngrok-skip-browser-warning'] = 'true';")
if "response.status === 422" not in content:
    content = content.replace("throw new Error(data.error || data.message || 'Request failed');",
                              "if (response.status === 422) { localStorage.clear(); window.location.href = '/'; } throw new Error(data.error || data.message || 'Request failed');")
with open(auth_js, "w") as f: f.write(content)

# --- 4. CONFIGURATION ---
with open(".env", "w") as f:
    f.writelines([
        "MONGO_URI=mongodb+srv://Dradmin:Mongo%40db%23123@cluster0.qa3itof.mongodb.net/\n",
        "MONGO_DB_NAME=NewAIEval\n",
        # Made this longer to fix the "InsecureKeyLengthWarning"
        "JWT_SECRET_KEY=colab-stable-session-secret-key-32-chars-long-v2\n",
        "JWT_ACCESS_TOKEN_EXPIRES=86400\n",
        "FLASK_DEBUG=0\n",
        "MAX_CONTENT_LENGTH=8388608\n",
        "MAX_CONCURRENT_EVALUATIONS=1\n",
        "MAX_PDF_PAGES=10\n",
        "NGROK_AUTH_TOKEN=3AbFUwuUiWdVY3KG97gvOnqiR18_7S56jZJzefkv21hPXGqar\n",
        "GEMINI_API_KEY=AIzaSyAwpECsPci4j2UEvnm1OvYtbPMbhYgSh3M\n"
    ])

# --- 5. LAUNCH ---
print("\n🚀 READY! Please UPLOAD A NEW FILE to test the system.")
!python start_with_ngrok.py
