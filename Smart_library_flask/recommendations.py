"""recommendations.py - the intelligent part of the system.

Machine Learning version:
- Content-based: TF-IDF vectorization + Cosine Similarity (text similarity on book metadata)
- Collaborative: K-Nearest Neighbors on a user-item interaction matrix
Combined into a hybrid ranking, same as before.

Function names are unchanged from the rule-based version, so nothing else
in the app (routes, templates) needs to be edited.
"""

import time
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors

# ---------------------------------------------------------------------------
# Simple in-memory cache — avoids retraining TF-IDF/KNN on every page load.
# Cache expires after CACHE_TTL_SECONDS, or can be force-cleared by calling
# invalidate_cache() (e.g. after an admin adds/edits/deletes a book).
# ---------------------------------------------------------------------------
CACHE_TTL_SECONDS = 300  # 5 minutes

_cache = {
    'books_df': None,
    'tfidf_matrix': None,
    'borrow_matrix': None,
    'trained_at': 0,
}


def invalidate_cache():
    """Call this after books/borrows change if you want instant refresh
    instead of waiting for the TTL to expire (optional, not required)."""
    _cache['books_df'] = None
    _cache['tfidf_matrix'] = None
    _cache['borrow_matrix'] = None
    _cache['trained_at'] = 0


def _cache_is_stale():
    return (time.time() - _cache['trained_at']) > CACHE_TTL_SECONDS


def _ensure_content_cache(db):
    if _cache['books_df'] is not None and not _cache_is_stale():
        return
    books_df = _get_all_books_df(db)
    if not books_df.empty and len(books_df) >= 2:
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(books_df['text_features'])
    else:
        tfidf_matrix = None
    _cache['books_df'] = books_df
    _cache['tfidf_matrix'] = tfidf_matrix
    _cache['trained_at'] = time.time()


def _ensure_collab_cache(db):
    if _cache['borrow_matrix'] is not None and not _cache_is_stale():
        return
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT user_id, book_id FROM borrow_logs")
    rows = cursor.fetchall()
    if rows:
        df = pd.DataFrame(rows)
        df['interaction'] = 1
        matrix = df.pivot_table(index='user_id', columns='book_id', values='interaction', fill_value=0)
    else:
        matrix = None
    _cache['borrow_matrix'] = matrix
    _cache['trained_at'] = time.time()


# ---------------------------------------------------------------------------
# Helpers: pull data out of MySQL into pandas, once per call
# ---------------------------------------------------------------------------

def _get_all_books_df(db):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM books")
    rows = cursor.fetchall()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df['text_features'] = (
        df['title'].fillna('') + ' ' +
        df['author'].fillna('') + ' ' +
        df['genre'].fillna('') + ' ' +
        df['description'].fillna('')
    )
    return df


def _get_borrowed_book_ids(db, user_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT book_id FROM borrow_logs WHERE user_id = %s", (user_id,))
    return {row['book_id'] for row in cursor.fetchall()}


def _get_liked_book_ids(db, user_id):
    """Books the user borrowed OR rated 4-5 stars — used as the 'taste profile'."""
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT book_id FROM borrow_logs WHERE user_id = %s
        UNION
        SELECT book_id FROM ratings WHERE user_id = %s AND rating >= 4
    """, (user_id, user_id))
    return [row['book_id'] for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# 1. Content-Based Filtering — TF-IDF + Cosine Similarity
# ---------------------------------------------------------------------------

def get_content_based_recommendations(db, user_id):
    """
    Uses TF-IDF to turn each book's title/author/genre/description into a
    vector, then finds books whose vectors are closest (cosine similarity)
    to the books this user already liked. This captures similarity in
    MEANING, not just an exact genre-label match.
    """
    _ensure_content_cache(db)
    books_df = _cache['books_df']
    tfidf_matrix = _cache['tfidf_matrix']
    if books_df is None or books_df.empty or tfidf_matrix is None:
        return {}

    liked_ids = _get_liked_book_ids(db, user_id)
    if not liked_ids:
        return {}

    borrowed_ids = _get_borrowed_book_ids(db, user_id)

    # Row positions (not DB ids) of the books this user liked
    id_to_index = {book_id: idx for idx, book_id in enumerate(books_df['id'])}
    liked_indices = [id_to_index[bid] for bid in liked_ids if bid in id_to_index]
    if not liked_indices:
        return {}

    # Similarity of every book to every liked book
    sim_matrix = cosine_similarity(tfidf_matrix[liked_indices], tfidf_matrix)
    # Average similarity across all liked books = this user's "taste profile"
    avg_similarity = sim_matrix.mean(axis=0)

    scored = {}
    for idx, score in enumerate(avg_similarity):
        book_id = int(books_df.iloc[idx]['id'])
        if book_id in borrowed_ids:
            continue
        if score > 0:
            scored[book_id] = float(score)

    return scored


# ---------------------------------------------------------------------------
# 2. Collaborative Filtering — K-Nearest Neighbors
# ---------------------------------------------------------------------------

def get_collaborative_recommendations(db, user_id):
    """
    Builds a user-item matrix (rows = users, columns = books, value = 1 if
    borrowed) and uses KNN with cosine distance to find the most similar
    users. Recommends books those neighbors borrowed that this user hasn't.
    """
    _ensure_collab_cache(db)
    matrix = _cache['borrow_matrix']
    if matrix is None or user_id not in matrix.index or len(matrix) < 2:
        return {}

    n_neighbors = min(6, len(matrix))  # target user + up to 5 neighbors
    model = NearestNeighbors(metric='cosine', algorithm='brute')
    model.fit(matrix.values)

    target_vector = matrix.loc[[user_id]].values
    distances, indices = model.kneighbors(target_vector, n_neighbors=n_neighbors)

    borrowed_ids = _get_borrowed_book_ids(db, user_id)

    scored = {}
    matrix_user_ids = matrix.index.tolist()
    for dist, idx in zip(distances[0], indices[0]):
        neighbor_id = matrix_user_ids[idx]
        if neighbor_id == user_id:
            continue
        similarity = 1 - dist  # cosine distance -> similarity
        if similarity <= 0:
            continue
        neighbor_books = matrix.columns[matrix.loc[neighbor_id] > 0]
        for book_id in neighbor_books:
            if book_id in borrowed_ids:
                continue
            scored[int(book_id)] = scored.get(int(book_id), 0) + similarity

    return scored


# ---------------------------------------------------------------------------
# 3. Hybrid — combine both, collaborative weighted higher
# ---------------------------------------------------------------------------

def get_hybrid_recommendations(db, user_id, limit=10):
    content_scores = get_content_based_recommendations(db, user_id)
    collab_scores = get_collaborative_recommendations(db, user_id)

    combined = {}
    for book_id, score in content_scores.items():
        combined[book_id] = combined.get(book_id, 0) + score
    for book_id, score in collab_scores.items():
        combined[book_id] = combined.get(book_id, 0) + (score * 2)

    if not combined:
        return []

    ranked_ids = sorted(combined, key=combined.get, reverse=True)[:limit]
    max_score = max(combined[bid] for bid in ranked_ids) or 1  # avoid divide-by-zero

    cursor = db.cursor(dictionary=True)
    placeholders = ','.join(['%s'] * len(ranked_ids))
    cursor.execute(f"SELECT * FROM books WHERE id IN ({placeholders})", tuple(ranked_ids))
    books_by_id = {book['id']: book for book in cursor.fetchall()}

    results = []
    for bid in ranked_ids:
        if bid not in books_by_id:
            continue
        book = dict(books_by_id[bid])
        # match_score: this book's combined score relative to the top match, as a %.
        # Shown on the recommendations page so the ML basis is visible, not a black box.
        book['match_score'] = round((combined[bid] / max_score) * 100)
        results.append(book)

    return results


def search_books(db, search_term, page=1, per_page=12):
    """Returns (books, total_count, total_pages) for the given page."""
    cursor = db.cursor(dictionary=True)
    page = max(1, page)
    offset = (page - 1) * per_page

    if search_term:
        term = f"%{search_term}%"
        cursor.execute(
            "SELECT COUNT(*) AS c FROM books WHERE title LIKE %s OR author LIKE %s OR genre LIKE %s",
            (term, term, term)
        )
        total_count = cursor.fetchone()['c']
        cursor.execute(
            "SELECT * FROM books WHERE title LIKE %s OR author LIKE %s OR genre LIKE %s "
            "ORDER BY title ASC LIMIT %s OFFSET %s",
            (term, term, term, per_page, offset)
        )
    else:
        cursor.execute("SELECT COUNT(*) AS c FROM books")
        total_count = cursor.fetchone()['c']
        cursor.execute(
            "SELECT * FROM books ORDER BY title ASC LIMIT %s OFFSET %s",
            (per_page, offset)
        )

    books = cursor.fetchall()
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    return books, total_count, total_pages


# ---------------------------------------------------------------------------
# BACKUP — original rule-based version (kept for instant revert if needed)
# ---------------------------------------------------------------------------
"""
def get_content_based_recommendations(db, user_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute('''
        SELECT b.genre, COUNT(*) AS genre_score
        FROM books b
        WHERE b.id IN (
            SELECT book_id FROM borrow_logs WHERE user_id = %s
            UNION ALL
            SELECT book_id FROM ratings WHERE user_id = %s AND rating >= 4
        )
        GROUP BY b.genre
        ORDER BY genre_score DESC
    ''', (user_id, user_id))
    favorite_genres = cursor.fetchall()

    if not favorite_genres:
        return {}

    genre_names = [row['genre'] for row in favorite_genres]
    placeholders = ','.join(['%s'] * len(genre_names))

    cursor.execute(f'''
        SELECT * FROM books
        WHERE genre IN ({placeholders})
        AND id NOT IN (SELECT book_id FROM borrow_logs WHERE user_id = %s)
    ''', (*genre_names, user_id))
    candidates = cursor.fetchall()

    genre_rank = {genre: i for i, genre in enumerate(genre_names)}
    scored = {}
    for book in candidates:
        rank = genre_rank.get(book['genre'], 99)
        scored[book['id']] = max(1, 5 - rank)

    return scored


def get_collaborative_recommendations(db, user_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute('''
        SELECT b2.user_id AS similar_user_id, COUNT(*) AS shared_books
        FROM borrow_logs b1
        JOIN borrow_logs b2 ON b1.book_id = b2.book_id AND b1.user_id != b2.user_id
        WHERE b1.user_id = %s
        GROUP BY b2.user_id
        ORDER BY shared_books DESC
        LIMIT 5
    ''', (user_id,))
    similar_users = cursor.fetchall()

    if not similar_users:
        return {}

    similar_user_ids = [row['similar_user_id'] for row in similar_users]
    shared_counts = {row['similar_user_id']: row['shared_books'] for row in similar_users}

    placeholders = ','.join(['%s'] * len(similar_user_ids))
    cursor.execute(f'''
        SELECT book_id, user_id FROM borrow_logs
        WHERE user_id IN ({placeholders})
        AND book_id NOT IN (SELECT book_id FROM borrow_logs WHERE user_id = %s)
    ''', (*similar_user_ids, user_id))
    rows = cursor.fetchall()

    scored = {}
    for row in rows:
        weight = shared_counts.get(row['user_id'], 1)
        scored[row['book_id']] = scored.get(row['book_id'], 0) + weight

    return scored
"""
