"""routes/book_routes.py - catalog, borrow, rate, return, history, recommendations."""

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from db import get_db
from auth import login_required, student_required
from recommendations import search_books, get_hybrid_recommendations

books_bp = Blueprint('books', __name__)

MAX_BORROWED_BOOKS = 3  # max books a student can have checked out at once


@books_bp.route('/')
@books_bp.route('/books')
@student_required
def books():
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    db = get_db()
    book_list, total_count, total_pages = search_books(db, search, page=page, per_page=12)
    db.close()

    return render_template('books.html', books=book_list, search=search,
                            page=page, total_pages=total_pages, total_count=total_count)


@books_bp.route('/borrow', methods=['POST'])
@login_required
def borrow():
    book_id = request.form['book_id']
    user_id = session['user_id']

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT available_copies FROM books WHERE id = %s", (book_id,))
    book = cursor.fetchone()

    cursor.execute(
        "SELECT id FROM borrow_logs WHERE user_id = %s AND book_id = %s AND status IN ('borrowed', 'overdue')",
        (user_id, book_id)
    )
    already_borrowed = cursor.fetchone()

    cursor.execute(
        "SELECT COUNT(*) AS active_count FROM borrow_logs WHERE user_id = %s AND status IN ('borrowed', 'overdue')",
        (user_id,)
    )
    active_count = cursor.fetchone()['active_count']

    success = False
    new_count = book['available_copies'] if book else 0
    message = ""

    if not book:
        message = "Book not found."
    elif already_borrowed:
        message = "You already have this book borrowed."
    elif active_count >= MAX_BORROWED_BOOKS:
        message = f"You've reached the limit of {MAX_BORROWED_BOOKS} borrowed books. Return one first."
    elif book['available_copies'] <= 0:
        message = "No copies available."
    else:
        cursor.execute("""
            INSERT INTO borrow_logs (user_id, book_id, borrow_date, due_date, status)
            VALUES (%s, %s, CURDATE(), DATE_ADD(CURDATE(), INTERVAL 14 DAY), 'borrowed')
        """, (user_id, book_id))
        cursor.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id = %s", (book_id,))
        db.commit()
        success = True
        new_count = book['available_copies'] - 1
        message = "Book borrowed!"

    cursor.close()
    db.close()

    # AJAX requests get JSON back; regular form submits (JS disabled) still redirect
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=success, available_copies=new_count, message=message)
    return redirect(url_for('books.books'))


@books_bp.route('/rate', methods=['POST'])
@login_required
def rate():
    book_id = request.form['book_id']
    rating = int(request.form['rating'])
    user_id = session['user_id']

    success = False
    if 1 <= rating <= 5:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO ratings (user_id, book_id, rating) VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE rating = %s
        """, (user_id, book_id, rating, rating))
        db.commit()
        cursor.close()
        db.close()
        success = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=success, rating=rating)
    return redirect(url_for('books.books'))


@books_bp.route('/return', methods=['POST'])
@login_required
def return_book():
    borrow_id = request.form['borrow_id']
    user_id = session['user_id']

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM borrow_logs WHERE id = %s AND user_id = %s AND status IN ('borrowed', 'overdue')",
        (borrow_id, user_id)
    )
    record = cursor.fetchone()

    if record:
        cursor.execute(
            "UPDATE borrow_logs SET return_date = CURDATE(), status = 'returned' WHERE id = %s",
            (borrow_id,)
        )
        cursor.execute(
            "UPDATE books SET available_copies = available_copies + 1 WHERE id = %s",
            (record['book_id'],)
        )
        db.commit()

    cursor.close()
    db.close()
    return redirect(url_for('books.history'))


@books_bp.route('/history')
@student_required
def history():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT bl.*, b.title, b.author,
               DATEDIFF(bl.due_date, CURDATE()) AS days_until_due
        FROM borrow_logs bl
        JOIN books b ON bl.book_id = b.id
        WHERE bl.user_id = %s
        ORDER BY bl.borrow_date DESC
    """, (session['user_id'],))
    records = cursor.fetchall()

    cursor.execute("SELECT book_id, rating FROM ratings WHERE user_id = %s", (session['user_id'],))
    my_ratings = {row['book_id']: row['rating'] for row in cursor.fetchall()}

    cursor.close()
    db.close()

    return render_template('history.html', history=records, my_ratings=my_ratings)


@books_bp.route('/recommendations')
@student_required
def recommendations():
    db = get_db()
    recs = get_hybrid_recommendations(db, session['user_id'])
    db.close()
    return render_template('recommendations.html', recommendations=recs)
