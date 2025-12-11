from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for, flash, Blueprint, session
from fernet import Fernet
import logging
import os

panel_bp = Blueprint('panel', __name__, template_folder='templates')
file_manager_instance = None
api_keys_dict = None
is_valid_key_func = None

def init_panel(file_manager, api_keys, is_valid_func):
    global file_manager_instance, api_keys_dict, is_valid_key_func
    file_manager_instance = file_manager
    api_keys_dict = api_keys
    is_valid_key_func = is_valid_func

@panel_bp.route("/panel")
def panel():
    if 'api_key' not in session or not is_valid_key_func(session['api_key']):
        return redirect(url_for('panel.login'))
    
    files = file_manager_instance.get_all_files()
    return render_template("panel.html", title="File Panel", files=files, logged_in=True)

@panel_bp.route("/panel/preview/<path:filename>")
def preview_file(filename):
    if 'api_key' not in session or not is_valid_key_func(session['api_key']):
        return "Unauthorized", 401
    
    try:
        file_path = os.path.join(file_manager_instance.upload_folder, filename)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return send_file(file_path)
        return "File not found", 404
    except Exception as e:
        return str(e), 500

@panel_bp.route("/panel/file-details/<path:filename>")
def file_details(filename):
    if 'api_key' not in session or not is_valid_key_func(session['api_key']):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        details = file_manager_instance.get_file_details(filename)
        return jsonify(details)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@panel_bp.route("/panel/file-content/<path:filename>")
def file_content(filename):
    if 'api_key' not in session or not is_valid_key_func(session['api_key']):
        return "Unauthorized", 401
    
    try:
        content = file_manager_instance.get_file_content(filename)
        return content
    except Exception as e:
        return str(e), 500

@panel_bp.route("/panel/save-file/<path:filename>", methods=["POST"])
def save_file(filename):
    if 'api_key' not in session or not is_valid_key_func(session['api_key']):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        content = request.json.get('content')
        file_manager_instance.save_file_content(filename, content)
        return jsonify({"success": True, "message": "File saved successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@panel_bp.route("/panel/upload", methods=["POST"])
def upload_file():
    if 'api_key' not in session or not is_valid_key_func(session['api_key']):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        filename = file_manager_instance.upload_file(file)
        return jsonify({"success": True, "message": "File uploaded successfully", "filename": filename})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@panel_bp.route("/panel/delete/<path:filename>", methods=["DELETE"])
def delete_file(filename):
    if 'api_key' not in session or not is_valid_key_func(session['api_key']):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        file_manager_instance.delete_file(filename)
        return jsonify({"success": True, "message": "File deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@panel_bp.route("/panel/create-folder", methods=["POST"])
def create_folder():
    if 'api_key' not in session or not is_valid_key_func(session['api_key']):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        folder_name = request.json.get('folder_name')
        if not folder_name:
            return jsonify({"error": "Folder name is required"}), 400
        
        file_manager_instance.create_folder(folder_name)
        return jsonify({"success": True, "message": "Folder created successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@panel_bp.route("/panel/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        api_key = request.form.get('api_key')
        if is_valid_key_func(api_key):
            session['api_key'] = api_key
            session.permanent = True  # Make session persistent across browser restarts
            return redirect(url_for('panel.panel'))
        else:
            return render_template("panel.html", title="Login", error="Invalid API Key", logged_in=False)
    return render_template("panel.html", title="Login", logged_in=False)

@panel_bp.route("/panel/logout")
def logout():
    session.pop('api_key', None)
    return redirect(url_for('panel.login'))

@panel_bp.route("/panel/api-keys", methods=["GET"])
def list_keys():
    if 'api_key' not in session or not is_valid_key_func(session['api_key']):
        return jsonify({"error": "Unauthorized"}), 401
    
    from datetime import datetime
    keys_info = []
    for key, expiry in api_keys_dict.items():
        info = {
            "key": key[:8] + "..." + key[-4:],
            "full_key": key,
            "type": "permanent" if expiry is None else "temporary",
            "is_current": key == session.get('api_key')
        }
        if expiry is not None:
            expiry_dt = datetime.fromtimestamp(expiry)
            info["expires_at"] = expiry_dt.isoformat()
            info["expires_in"] = str(expiry_dt - datetime.now()).split('.')[0]
        keys_info.append(info)
    
    return jsonify({"api_keys": keys_info, "total": len(keys_info)})

@panel_bp.route("/panel/api-keys/create", methods=["POST"])
def create_key():
    if 'api_key' not in session or not is_valid_key_func(session['api_key']):
        return jsonify({"error": "Unauthorized"}), 401
    
    from fernet import Fernet
    from datetime import datetime, timedelta
    
    data = request.get_json() or {}
    new_key = Fernet.generate_key().decode()
    
    expiry_datetime = data.get('expiry_datetime')
    if expiry_datetime:
        try:
            # Parse ISO format datetime
            expiry = datetime.fromisoformat(expiry_datetime.replace('Z', '+00:00'))
            
            # Ensure it's in the future
            if expiry <= datetime.now():
                return jsonify({"error": "Expiration date must be in the future"}), 400
            
            # Check it's not more than 1 year in the future
            max_expiry = datetime.now() + timedelta(days=365)
            if expiry > max_expiry:
                return jsonify({"error": "Expiration date cannot be more than 1 year in the future"}), 400
            
            api_keys_dict[new_key] = expiry.timestamp()
            return jsonify({
                "success": True,
                "api_key": new_key,
                "temporary": True,
                "expires_at": expiry.isoformat()
            })
        except (ValueError, AttributeError) as e:
            return jsonify({"error": f"Invalid datetime format: {str(e)}"}), 400
    
    # Create permanent key
    api_keys_dict[new_key] = None
    return jsonify({"success": True, "api_key": new_key, "temporary": False})

@panel_bp.route("/panel/api-keys/delete", methods=["DELETE"])
def delete_key():
    if 'api_key' not in session or not is_valid_key_func(session['api_key']):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    key_to_delete = data.get('api_key')
    
    if not key_to_delete:
        return jsonify({"error": "API key is required"}), 400
    
    if key_to_delete == session.get('api_key'):
        return jsonify({"error": "Cannot delete the key you're currently using"}), 400
    
    if key_to_delete in api_keys_dict:
        del api_keys_dict[key_to_delete]
        return jsonify({"success": True, "message": "API key deleted successfully"})
    else:
        return jsonify({"error": "API key not found"}), 404