"""routes/admin_routes.py - admin book management panel."""

import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, current_app, redirect, url_for
from db import get_db
from auth import admin_required
from recommendations import search_books
from cover_fetcher import fetch_and_save_cover
from book_lookup import lookup_book_by_title
from flask import jsonify

admin_bp = Blueprint('admin', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route('/admin', methods=['GET', 'POST'])
@admin_required
def admin_books():
    error = None
    success = None
    db = get_db()
    cursor = db.cursor(dictionary=True)

    delete_id = request.args.get('delete')
    if delete_id:
        cursor.execute("DELETE FROM books WHERE id = %s", (delete_id,))
        db.commit()
        success = "Book deleted."

    if request.method == 'POST':
        title = request.form['title'].strip()
        author = request.form['author'].strip()
        genre = request.form['genre'].strip()
        description = request.form['description'].strip()
        isbn = request.form['isbn'].strip()
        total_copies = int(request.form['total_copies'])
        book_id = request.form.get('book_id')

        upload_folder = os.path.join(current_app.root_path, 'static', 'covers')

        # 1. Check for a manually uploaded cover first
        cover_filename = None
        file = request.files.get('cover_image')
        if file and file.filename and allowed_file(file.filename):
            safe_name = secure_filename(file.filename)
            cover_filename = f"{title.replace(' ', '_').lower()}_{safe_name}"
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, cover_filename))

        # 2. If nothing was manually uploaded, try auto-fetching a real cover
        auto_fetch_note = ""
        if not cover_filename:
            cover_filename = fetch_and_save_cover(isbn, title, author, upload_folder)
            if cover_filename:
                auto_fetch_note = " (cover auto-fetched)"

        if not title or not genre:
            error = "Title and genre are required."
        elif total_copies < 0:
            error = "Total copies cannot be negative."
        elif book_id:
            cursor.execute("SELECT total_copies, available_copies, cover_image FROM books WHERE id = %s", (book_id,))
            row = cursor.fetchone()
            diff = total_copies - row['total_copies']
            new_available = max(0, min(total_copies, row['available_copies'] + diff))
            # Keep the existing cover if nothing new was uploaded or auto-fetched
            final_cover = cover_filename if cover_filename else row['cover_image']

            cursor.execute("""
                UPDATE books SET title=%s, author=%s, genre=%s, description=%s, isbn=%s,
                total_copies=%s, available_copies=%s, cover_image=%s WHERE id=%s
            """, (title, author, genre, description, isbn, total_copies, new_available, final_cover, book_id))
            db.commit()
            success = f"Book updated.{auto_fetch_note}"
        else:
            cursor.execute("""
                INSERT INTO books (title, author, genre, description, isbn, total_copies, available_copies, cover_image)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (title, author, genre, description, isbn, total_copies, total_copies, cover_filename))
            db.commit()
            success = f"Book added.{auto_fetch_note}"

    edit_book = None
    edit_id = request.args.get('edit')
    if edit_id:
        cursor.execute("SELECT * FROM books WHERE id = %s", (edit_id,))
        edit_book = cursor.fetchone()

    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    book_list, total_count, total_pages = search_books(db, search, page=page, per_page=10)

    cursor.close()
    db.close()

    return render_template('admin.html', books=book_list, edit_book=edit_book,
                            search=search, error=error, success=success,
                            page=page, total_pages=total_pages, total_count=total_count)


@admin_bp.route('/admin/books/history')
@admin_required
def books_history_overview():
    """Overview list of all books with quick borrow/rating stats, linking into each book's detail page."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT b.id, b.title, b.author, b.genre,
               COUNT(DISTINCT bl.id) AS times_borrowed,
               ROUND(AVG(r.rating), 1) AS avg_rating,
               COUNT(DISTINCT r.id) AS rating_count
        FROM books b
        LEFT JOIN borrow_logs bl ON bl.book_id = b.id
        LEFT JOIN ratings r ON r.book_id = b.id
        GROUP BY b.id
        ORDER BY times_borrowed DESC, b.title ASC
    """)
    overview = cursor.fetchall()
    cursor.close()
    db.close()
    return render_template('books_history_overview.html', overview=overview)


@admin_bp.route('/admin/book/<int:book_id>/history')
@admin_required
def book_history(book_id):
    """Shows who has borrowed a specific book (with dates/status) and its ratings."""
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM books WHERE id = %s", (book_id,))
    book = cursor.fetchone()
    if not book:
        db.close()
        return redirect(url_for('admin.admin_books'))

    cursor.execute("""
        SELECT bl.*, u.name AS user_name, u.email AS user_email
        FROM borrow_logs bl
        JOIN users u ON bl.user_id = u.id
        WHERE bl.book_id = %s
        ORDER BY bl.borrow_date DESC
    """, (book_id,))
    borrow_history = cursor.fetchall()

    cursor.execute("""
        SELECT r.rating, r.created_at, u.name AS user_name
        FROM ratings r
        JOIN users u ON r.user_id = u.id
        WHERE r.book_id = %s
        ORDER BY r.created_at DESC
    """, (book_id,))
    rating_list = cursor.fetchall()

    cursor.execute("SELECT AVG(rating) AS avg_rating, COUNT(*) AS rating_count FROM ratings WHERE book_id = %s", (book_id,))
    rating_summary = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template('book_history.html', book=book, borrow_history=borrow_history,
                            rating_list=rating_list, rating_summary=rating_summary)


@admin_bp.route('/admin/book-lookup')
@admin_required
def book_lookup():
    """Called via fetch() from the admin form's 'Auto-fill' button."""
    title = request.args.get('title', '').strip()
    result = lookup_book_by_title(title)

    if result:
        return jsonify(success=True, book=result)
    return jsonify(success=False, message="No matching book found.")


@admin_bp.route('/admin/fetch-missing-covers')
@admin_required
def fetch_missing_covers():
    """Bulk backfill: tries to auto-fetch covers for every book that doesn't have one yet."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, title, author, isbn FROM books WHERE cover_image IS NULL OR cover_image = ''")
    missing = cursor.fetchall()

    upload_folder = os.path.join(current_app.root_path, 'static', 'covers')
    found_count = 0

    for book in missing:
        filename = fetch_and_save_cover(book['isbn'], book['title'], book['author'], upload_folder)
        if filename:
            update = db.cursor()
            update.execute("UPDATE books SET cover_image = %s WHERE id = %s", (filename, book['id']))
            db.commit()
            update.close()
            found_count += 1

    cursor.close()
    db.close()

    # Redirect back to the admin panel; the count shows via a query param
    return redirect(url_for('admin.admin_books', covers_found=found_count, covers_checked=len(missing)))


@admin_bp.route('/admin/borrowed', methods=['GET', 'POST'])
@admin_required
def borrowed_books():
    """Shows every currently borrowed book with its due date, so admin can send
    a manual reminder to a specific user on top of the automatic ones."""
    from notifications import send_manual_reminder

    db = get_db()
    cursor = db.cursor(dictionary=True)
    sent_message = None

    if request.method == 'POST':
        borrow_id = request.form['borrow_id']
        user_id = request.form['user_id']
        book_title = request.form['book_title']
        due_date = request.form['due_date']

        message = f"Reminder from the library: please return \"{book_title}\" (due {due_date})."
        send_manual_reminder(db, user_id, message, borrow_id)
        sent_message = f"Reminder sent for \"{book_title}\"."

    cursor.execute("""
        SELECT bl.id AS borrow_id, bl.due_date, bl.borrow_date,
               DATEDIFF(bl.due_date, CURDATE()) AS days_until_due,
               b.title, u.id AS user_id, u.name AS user_name, u.email AS user_email
        FROM borrow_logs bl
        JOIN books b ON bl.book_id = b.id
        JOIN users u ON bl.user_id = u.id
        WHERE bl.status = 'borrowed'
        ORDER BY bl.due_date ASC
    """)
    active_borrows = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template('admin_borrowed.html', borrows=active_borrows, sent_message=sent_message)
