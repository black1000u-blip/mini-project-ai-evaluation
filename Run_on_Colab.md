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


# --- 5. LAUNCH ---
print("\n🚀 READY! Please UPLOAD A NEW FILE to test the system.")
!python start_with_ngrok.py
