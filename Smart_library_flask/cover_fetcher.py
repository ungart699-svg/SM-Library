"""cover_fetcher.py - automatically finds and downloads real book cover images.

Tries, in order:
1. Open Library's cover API, matched by ISBN (fastest, most reliable when ISBN is correct)
2. Google Books API, matched by title + author (fallback when no ISBN or no OL match)
"""

import os
import requests
from config import GOOGLE_BOOKS_API_KEY


def fetch_cover_openlibrary(isbn):
    """Try to get a cover image from Open Library using the book's ISBN."""
    if not isbn:
        return None

    isbn_clean = isbn.replace('-', '').strip()
    url = f"https://covers.openlibrary.org/b/isbn/{isbn_clean}-L.jpg?default=false"

    try:
        response = requests.get(url, timeout=6)
        # Open Library returns a real image only if it exists; 'default=false' avoids
        # getting back a blank placeholder image for unknown ISBNs.
        if response.status_code == 200 and len(response.content) > 1000:
            return response.content
    except requests.RequestException:
        pass

    return None


def fetch_cover_google_books(title, author):
    """Fallback: search Google Books by title/author and grab the thumbnail."""
    query = f"intitle:{title}"
    if author:
        query += f"+inauthor:{author}"

    try:
        response = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": query, "maxResults": 1, "langRestrict": "en", "key": GOOGLE_BOOKS_API_KEY},
            timeout=6
        )
        data = response.json()
        items = data.get('items', [])
        if not items:
            return None

        image_links = items[0].get('volumeInfo', {}).get('imageLinks', {})
        img_url = image_links.get('thumbnail') or image_links.get('smallThumbnail')
        if not img_url:
            return None

        # Google sometimes returns http:// links; force https to avoid mixed-content issues
        img_url = img_url.replace('http://', 'https://')
        img_response = requests.get(img_url, timeout=6)
        if img_response.status_code == 200:
            return img_response.content
    except requests.RequestException:
        pass

    return None


def fetch_and_save_cover(isbn, title, author, save_folder):
    """
    Tries both sources in order, saves the first successful result to disk,
    and returns the filename to store in the database (or None if nothing found).
    """
    os.makedirs(save_folder, exist_ok=True)

    image_bytes = fetch_cover_openlibrary(isbn)
    source = 'ol'

    if not image_bytes:
        image_bytes = fetch_cover_google_books(title, author)
        source = 'gb'

    if not image_bytes:
        return None

    safe_title = "".join(c for c in title if c.isalnum() or c == ' ').replace(' ', '_').lower()
    filename = f"{safe_title}_{source}.jpg"
    filepath = os.path.join(save_folder, filename)

    with open(filepath, 'wb') as f:
        f.write(image_bytes)

    return filename
