"""notifications.py - due-date reminders, both automatic and admin-sent."""

DUE_SOON_DAYS = 2  # a book counts as "due soon" within this many days of its due date


def update_overdue_statuses(db):
    """
    Automatically flips any borrow whose due_date has passed from
    'borrowed' to 'overdue'. Runs on every page load (called from app.py's
    context processor), so status stays accurate without needing a separate
    scheduled task/cron job.
    """
    cursor = db.cursor(buffered=True)
    cursor.execute("""
        UPDATE borrow_logs
        SET status = 'overdue'
        WHERE status = 'borrowed' AND due_date < CURDATE()
    """)
    db.commit()
    cursor.close()


def generate_due_date_reminders(db, user_id):
    """
    Checks this user's currently borrowed books. For any that are overdue or
    due within DUE_SOON_DAYS, creates a reminder notification — but only once
    per borrow (checked via the borrow_id link), so refreshing the page
    doesn't spam duplicate reminders.
    """
    cursor = db.cursor(dictionary=True, buffered=True)
    cursor.execute("""
        SELECT bl.id AS borrow_id, bl.due_date, b.title,
               DATEDIFF(bl.due_date, CURDATE()) AS days_until_due
        FROM borrow_logs bl
        JOIN books b ON bl.book_id = b.id
        WHERE bl.user_id = %s AND bl.status IN ('borrowed', 'overdue')
        AND DATEDIFF(bl.due_date, CURDATE()) <= %s
    """, (user_id, DUE_SOON_DAYS))
    at_risk = cursor.fetchall()

    for item in at_risk:
        # Skip if a reminder for this exact borrow already exists
        cursor.execute(
            "SELECT id FROM notifications WHERE borrow_id = %s AND user_id = %s",
            (item['borrow_id'], user_id)
        )
        if cursor.fetchone():
            continue

        if item['days_until_due'] < 0:
            message = f"Your book \"{item['title']}\" is overdue. Please return it as soon as possible."
        elif item['days_until_due'] == 0:
            message = f"Your book \"{item['title']}\" is due today. Please return it soon."
        else:
            message = f"Reminder: \"{item['title']}\" is due in {item['days_until_due']} day(s)."

        insert = db.cursor(buffered=True)
        insert.execute(
            "INSERT INTO notifications (user_id, borrow_id, message) VALUES (%s, %s, %s)",
            (user_id, item['borrow_id'], message)
        )
        db.commit()
        insert.close()

    cursor.close()


def send_manual_reminder(db, user_id, message, borrow_id=None):
    """Used by the admin panel to send a one-off custom reminder to a specific user."""
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "INSERT INTO notifications (user_id, borrow_id, message) VALUES (%s, %s, %s)",
        (user_id, borrow_id, message)
    )
    db.commit()
    cursor.close()


def get_unread_count(db, user_id):
    cursor = db.cursor(buffered=True)
    cursor.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = %s AND is_read = 0",
        (user_id,)
    )
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def get_notifications(db, user_id, limit=20):
    cursor = db.cursor(dictionary=True, buffered=True)
    cursor.execute("""
        SELECT * FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """, (user_id, limit))
    results = cursor.fetchall()
    cursor.close()
    return results


def mark_all_read(db, user_id):
    cursor = db.cursor(buffered=True)
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = %s", (user_id,))
    db.commit()
    cursor.close()
