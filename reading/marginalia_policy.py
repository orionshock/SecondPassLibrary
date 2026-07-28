def include_marginalia_session(
    *, annotation_count: int, include_empty_sessions: bool
) -> bool:
    """Return whether a Session belongs in an import/export workflow."""
    return include_empty_sessions or annotation_count > 0
