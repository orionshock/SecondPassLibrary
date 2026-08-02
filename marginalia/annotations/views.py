from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from marginalia.api import (
    MarginaliaReadMixin,
    book_access_required_response,
    session_closed_response,
)
from marginalia.exceptions import BookAccessRequiredError, SessionClosedError
from marginalia.models import ReadingSession

from .collection import annotation_collection
from .serializers import AnnotationBatchSerializer
from .services import synchronize_annotations


class SessionAnnotationListView(MarginaliaReadMixin, APIView):
    def get(self, request, session_id):
        session = get_object_or_404(
            ReadingSession,
            pk=session_id,
            user=request.user,
        )
        return Response(annotation_collection(session))


class SessionAnnotationBatchView(MarginaliaReadMixin, APIView):
    def post(self, request, session_id):
        serializer = AnnotationBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session = synchronize_annotations(
                user=request.user,
                session_id=session_id,
                operations=serializer.validated_data["operations"],
            )
        except ReadingSession.DoesNotExist as exc:
            raise NotFound from exc
        except SessionClosedError:
            return session_closed_response()
        except BookAccessRequiredError:
            return book_access_required_response()
        return Response(annotation_collection(session))
