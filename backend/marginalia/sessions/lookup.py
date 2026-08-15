from marginalia.models import ReadingSession


def locked_owned_session(*, user, session_id) -> ReadingSession:
    return ReadingSession.objects.select_for_update().get(
        pk=session_id,
        user=user,
    )
