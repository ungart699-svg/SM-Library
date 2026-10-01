"""routes/auth_routes.py - signup, login, logout."""

from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    success = None

    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        password = request.form['password']

        if not name or not email or not password:
            error = "Please fill in all fields."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            db = get_db()
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                error = "An account with that email already exists."
            else:
                hashed = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, 'student')",
                    (name, email, hashed)
                )
                db.commit()
                success = "Account created! You can now log in."
            cursor.close()
            db.close()

    return render_template('signup.html', error=error, success=success)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']

        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            session['profile_picture'] = user.get('profile_picture')
            return redirect(url_for('admin.admin_books' if user['role'] == 'admin' else 'books.books'))
        else:
            error = "Invalid email or password."

    return render_template('login.html', error=error)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
