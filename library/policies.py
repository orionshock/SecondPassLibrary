from __future__ import annotations


def can_manage_library(user) -> bool:
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
    )


def can_import_books(user) -> bool:
    return can_manage_library(user)


def can_view_book(*, user, book) -> bool:
    return can_manage_library(user)


def can_download_book_file(*, user, book_file) -> bool:
    return can_manage_library(user)


def can_create_library_group(user) -> bool:
    return can_manage_library(user)


def can_delete_library_group(user, group=None) -> bool:
    return can_manage_library(user)


def can_manage_group_identity(*, user, group) -> bool:
    return can_manage_library(user)


def can_manage_group_membership(*, user, group) -> bool:
    return can_manage_library(user)


def can_manage_group_books(*, user, group) -> bool:
    return can_manage_library(user)


def can_edit_group_presentation(*, user, group) -> bool:
    return can_manage_library(user)


def can_edit_group_description(*, user, group) -> bool:
    return can_manage_library(user)


def can_view_library_group(*, user, group) -> bool:
    return can_manage_library(user)


def can_curate_group(*, user, group) -> bool:
    return can_manage_library(user)


def can_add_book_to_group(*, user, book, group) -> bool:
    return can_manage_library(user)


def can_remove_book_from_group(*, user, book, group) -> bool:
    return can_manage_library(user)
