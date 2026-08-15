from library.queries import visible_books_for_user
from marginalia.exceptions import BookAccessRequiredError


def require_book_access(*, user, book_id) -> None:
    if not visible_books_for_user(user, cached=False).filter(pk=book_id).exists():
        raise BookAccessRequiredError
