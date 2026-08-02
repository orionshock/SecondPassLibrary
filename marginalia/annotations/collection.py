from django.db.models import Case, IntegerField, QuerySet, Value, When

from marginalia.models import Annotation, ReadingSession

from .serializers import AnnotationCollectionSerializer


def annotations_for_session(session: ReadingSession) -> QuerySet[Annotation]:
    return (
        Annotation.objects.filter(session=session, is_deleted=False)
        .annotate(
            _blank_location_label=Case(
                When(location_label="", then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by(
            "_blank_location_label",
            "location_label",
            "cfi",
            "created_at",
            "id",
        )
    )


def annotation_collection(session: ReadingSession) -> dict:
    return AnnotationCollectionSerializer(
        {"annotations": annotations_for_session(session)}
    ).data
