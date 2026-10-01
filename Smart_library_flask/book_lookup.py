"""book_lookup.py - fetches book metadata (author, genre, description, ISBN)
from Google Books based on a title. Used by the admin panel's Auto-fill button.
"""

import requests
from config import GOOGLE_BOOKS_API_KEY


def lookup_book_by_title(title):
    """
    Searches Google Books by title and returns the book's metadata:
    author, description, genre (from categories), and ISBN.
    Returns None if nothing found.
    """
    if not title or not title.strip():
        return None

    try:
        response = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={
                "q": f"intitle:{title.strip()}",
                "maxResults": 5,
                "langRestrict": "en",   # asks Google to prefer English-language results
                "key": GOOGLE_BOOKS_API_KEY
            },
            timeout=6
        )
        data = response.json()
        items = data.get('items', [])
        if not items:
            return None

        # langRestrict is a soft hint, not a guarantee — double check and prefer
        # an item actually marked as English if one exists in the results
        info = None
        for candidate in items:
            candidate_info = candidate.get('volumeInfo', {})
            if candidate_info.get('language') == 'en':
                info = candidate_info
                break
        if info is None:
            info = items[0].get('volumeInfo', {})

        # Authors come back as a list; join multiple authors with commas
        authors = info.get('authors', [])
        author = ", ".join(authors) if authors else ""

        # Categories are Google's loose genre tags; take the first one
        categories = info.get('categories', [])
        genre = categories[0] if categories else ""

        description = info.get('description', "")
        # Google's descriptions can be long/HTML-ish; keep it reasonably short and plain
        if len(description) > 500:
            description = description[:497] + "..."

        # ISBN comes as a list of identifier objects; prefer ISBN_13, fall back to ISBN_10
        isbn = ""
        for identifier in info.get('industryIdentifiers', []):
            if identifier.get('type') == 'ISBN_13':
                isbn = identifier.get('identifier', "")
                break
        if not isbn:
            for identifier in info.get('industryIdentifiers', []):
                if identifier.get('type') == 'ISBN_10':
                    isbn = identifier.get('identifier', "")
                    break

        return {
            "title": info.get('title', title),
            "author": author,
            "genre": genre,
            "description": description,
            "isbn": isbn
        }
    except requests.RequestException:
        return None
