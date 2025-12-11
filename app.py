from flask import Flask, render_template, request, send_file, jsonify
from fernet import Fernet
import logging
import os
from werkzeug.utils import secure_filename
import file_manager
from panel import panel_bp, init_panel
import atexit
from datetime import timedelta, datetime
import json

app = Flask(__name__)
app.secret_key = Fernet.generate_key().decode()

# Session configuration for persistent cookies
app.config['SESSION_COOKIE_NAME'] = 'flask_file_storage_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # Sessions last 30 days

UPLOAD_FOLDER = "data"
CONFIG_FOLDER = "config"
API_KEYS_FILE = os.path.join(CONFIG_FOLDER, "api_keys.txt")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONFIG_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

file_manager = file_manager.FileManager(UPLOAD_FOLDER)

api_keys = {}
TEMP_KEYS_FILE = os.path.join(CONFIG_FOLDER, "temp_keys.json")

try:
    with open(API_KEYS_FILE, "r") as f:
        for line in f:
            key = line.strip()
            if key:
                api_keys[key] = None  # None means permanent
except FileNotFoundError:
    new_key = Fernet.generate_key().decode()
    api_keys[new_key] = None
    logging.error("api_keys.txt not found. Generated a new API key.")

# Load temporary keys
try:
    with open(TEMP_KEYS_FILE, "r") as f:
        temp_keys = json.load(f)
        for key, expiry in temp_keys.items():
            # Only load keys that haven't expired
            if expiry and datetime.fromtimestamp(expiry) > datetime.now():
                api_keys[key] = expiry
except (FileNotFoundError, json.JSONDecodeError):
    pass

# Get first permanent key for display
permanent_keys = [k for k, v in api_keys.items() if v is None]
if permanent_keys:
    print("API Key:", permanent_keys[0])
else:
    print("No permanent API keys found")

def is_valid_api_key(key):
    """Check if API key is valid and not expired"""
    if key not in api_keys:
        return False
    
    expiry = api_keys[key]
    if expiry is None:  # Permanent key
        return True
    
    # Check if temporary key has expired
    if datetime.fromtimestamp(expiry) > datetime.now():
        return True
    else:
        # Remove expired key
        del api_keys[key]
        return False

init_panel(file_manager, api_keys, is_valid_api_key)
app.register_blueprint(panel_bp)

def save_api_keys():
    # Save permanent keys
    with open(API_KEYS_FILE, "w") as f:
        for key, expiry in api_keys.items():
            if expiry is None:  # Only save permanent keys
                f.write(f"{key}\n")
    
    # Save temporary keys that haven't expired
    temp_keys = {k: v for k, v in api_keys.items() if v is not None and datetime.fromtimestamp(v) > datetime.now()}
    with open(TEMP_KEYS_FILE, "w") as f:
        json.dump(temp_keys, f)

atexit.register(save_api_keys)

@app.route("/")
def hello_world():
    return render_template("index.html", title="Hello")

@app.route("/health")
def health_check():
    return jsonify({
        "status": "healthy",
        "upload_folder": UPLOAD_FOLDER,
        "config_folder": CONFIG_FOLDER,
        "api_keys_loaded": len(api_keys)
    }), 200

@app.route("/api-keys/create", methods=["GET", "POST"])
def create_api_key():
    auth_key = request.headers.get('API-KEY')
    if not is_valid_api_key(auth_key):
        return {"error": "Unauthorized"}, 401
    
    new_key = Fernet.generate_key().decode()
    
    # Check if this should be a temporary key
    if request.method == "POST":
        data = request.get_json() or {}
        hours = data.get('hours')
        if hours:
            try:
                hours = int(hours)
                if hours > 0 and hours <= 8760:  # Max 1 year
                    expiry = datetime.now() + timedelta(hours=hours)
                    api_keys[new_key] = expiry.timestamp()
                    return {
                        "api_key": new_key,
                        "temporary": True,
                        "expires_at": expiry.isoformat(),
                        "expires_in_hours": hours
                    }
                else:
                    return {"error": "Hours must be between 1 and 8760"}, 400
            except ValueError:
                return {"error": "Invalid hours value"}, 400
    
    # Default: create permanent key
    api_keys[new_key] = None
    return {"api_key": new_key, "temporary": False}

@app.route("/api-keys/delete", methods=["DELETE"])
def delete_api_key():
    auth_key = request.headers.get('API-KEY')
    if not is_valid_api_key(auth_key):
        return {"error": "Unauthorized"}, 401
    
    data = request.get_json()
    key_to_delete = data.get('api_key')
    
    if not key_to_delete:
        return {"error": "API key is required"}, 400
    
    # Prevent deleting the key being used for authentication
    if key_to_delete == auth_key:
        return {"error": "Cannot delete the key you're currently using"}, 400
    
    if key_to_delete in api_keys:
        del api_keys[key_to_delete]
        save_api_keys()
        return {"message": "API key deleted successfully"}
    else:
        return {"error": "API key not found"}, 404

@app.route("/api-keys/list", methods=["GET"])
def list_api_keys():
    auth_key = request.headers.get('API-KEY')
    if not is_valid_api_key(auth_key):
        return {"error": "Unauthorized"}, 401
    
    keys_info = []
    for key, expiry in api_keys.items():
        info = {
            "key": key[:8] + "..." + key[-4:],  # Masked for security
            "full_key": key,
            "type": "permanent" if expiry is None else "temporary"
        }
        if expiry is not None:
            expiry_dt = datetime.fromtimestamp(expiry)
            info["expires_at"] = expiry_dt.isoformat()
            info["expires_in"] = str(expiry_dt - datetime.now())
        keys_info.append(info)
    
    return {"api_keys": keys_info, "total": len(keys_info)}

@app.route("/get", methods=["GET"])
def get():
    filename = request.args.get('filename')
    if not filename:
        return "Filename is required", 400
    
    try:
        safe_filename = secure_filename(filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        
        if os.path.exists(file_path):
            return send_file(file_path)
        else:
            return "File not found", 404
    except Exception as e:
        logging.error(f"Error retrieving file: {str(e)}")
        return f"Error: {str(e)}", 500

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        api_key = request.headers.get('API-KEY')
        if is_valid_api_key(api_key):
            try:
                if 'file' not in request.files:
                    return "No file part in request", 400

                file = request.files['file']
                if file.filename == '':
                    return "No selected file", 400

                target_folder = request.form.get('folder', '')
                
                return file_manager.save_file(file, target_folder)

            except Exception as e:
                logging.error(f"Error adding item: {str(e)}")
                return f"Error: {str(e)}", 400
            finally:
                logging.info(f"Add item attempt with API-KEY: {api_key}")
        else:
            return "Unauthorized", 401
    return render_template("add.html", title="Add Item")

app.run(debug=True, host='0.0.0.0', port=5000)
