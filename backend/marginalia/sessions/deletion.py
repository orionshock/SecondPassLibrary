import logging

from django.db import transaction

from core.operational_logging import info_on_commit, user_uuid
from marginalia.models import Annotation

from .lookup import locked_owned_session


logger = logging.getLogger("marginalia.sessions.services")


@transaction.atomic
def delete_owned_session(*, user, session_id) -> None:
    session = locked_owned_session(user=user, session_id=session_id)
    deleted_session_id = str(session.pk)
    book_id = str(session.book_id)
    previous_status = session.status
    owner_id = user_uuid(user)

    _, deleted_by_model = session.delete()
    annotation_count = deleted_by_model.get(Annotation._meta.label, 0)
    info_on_commit(
        logger,
        "Marginalia Reading Session deleted: session=%s owner=%s book=%s "
        "previous_status=%s annotation_count=%d",
        deleted_session_id,
        owner_id,
        book_id,
        previous_status,
        annotation_count,
    )
