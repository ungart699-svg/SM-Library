"""routes/notification_routes.py - viewing and clearing notifications."""

from flask import Blueprint, render_template, session, redirect, url_for
from db import get_db
from auth import login_required
from notifications import get_notifications, mark_all_read, generate_due_date_reminders

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/notifications')
@login_required
def notifications():
    db = get_db()

    # Refresh due-date reminders every time this page is viewed
    generate_due_date_reminders(db, session['user_id'])

    notes = get_notifications(db, session['user_id'])
    mark_all_read(db, session['user_id'])  # viewing the page counts as reading them

    db.close()
    return render_template('notifications.html', notifications=notes)
