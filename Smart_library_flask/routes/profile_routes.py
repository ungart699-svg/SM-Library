"""routes/profile_routes.py - profile picture upload, available to any logged-in user."""

import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, session, current_app, redirect, url_for
from db import get_db
from auth import login_required

profile_bp = Blueprint('profile', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@profile_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    error = None
    success = None
    user_id = session['user_id']

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        file = request.files.get('profile_picture')

        if not file or not file.filename:
            error = "Please choose an image to upload."
        elif not allowed_file(file.filename):
            error = "Please upload a PNG, JPG, GIF, or WEBP image."
        else:
            # Filename keyed by user_id so re-uploading always replaces the old one
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = secure_filename(f"user_{user_id}.{ext}")

            upload_folder = os.path.join(current_app.root_path, 'static', 'profile_pics')
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, filename))

            cursor.execute("UPDATE users SET profile_picture = %s WHERE id = %s", (filename, user_id))
            db.commit()
            session['profile_picture'] = filename  # keep session in sync so the navbar updates immediately
            success = "Profile picture updated!"

    cursor.execute("SELECT name, email, role, profile_picture FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    cursor.close()
    db.close()

    template = 'admin_profile.html' if session.get('user_role') == 'admin' else 'profile.html'
    return render_template(template, user=user, error=error, success=success)
