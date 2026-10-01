"""auth.py - login/role-checking decorators, used to protect routes."""

from flask import session, redirect, url_for
from functools import wraps

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper

def student_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('user_role') == 'admin':
            return redirect(url_for('admin.admin_books'))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('user_role') != 'admin':
            return "Access denied. This page is for admins only.", 403
        return f(*args, **kwargs)
    return wrapper
