"""
app.py - Smart Library Recommendation System (Flask)
This file just creates the app and wires everything together.
All actual logic lives in db.py, auth.py, recommendations.py, and routes/
"""

from flask import Flask, session
from routes.auth_routes import auth_bp
from routes.book_routes import books_bp
from routes.admin_routes import admin_bp
from routes.profile_routes import profile_bp
from routes.notification_routes import notifications_bp
from db import get_db
from notifications import get_unread_count, generate_due_date_reminders, update_overdue_statuses

app = Flask(__name__)
app.secret_key = 'change-this-to-something-random'  # needed for sessions

app.register_blueprint(auth_bp)
app.register_blueprint(books_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(notifications_bp)


@app.context_processor
def inject_unread_notifications():
    """Makes 'unread_notifications' available in every template automatically,
    flips overdue borrows, and generates any new due-date reminders as pages load."""
    if 'user_id' in session:
        db = get_db()
        update_overdue_statuses(db)  # runs for any logged-in user, keeps status current system-wide
        if session.get('user_role') != 'admin':
            generate_due_date_reminders(db, session['user_id'])
            count = get_unread_count(db, session['user_id'])
        else:
            count = 0
        db.close()
        return dict(unread_notifications=count)
    return dict(unread_notifications=0)

if __name__ == '__main__':
    # host='0.0.0.0' makes this reachable from other devices on your network,
    # not just from this PC via 'localhost'.
    app.run(debug=True, host='0.0.0.0', port=5000)
