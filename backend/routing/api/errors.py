import logging

from django.core.exceptions import RequestDataTooBig
from rest_framework import status
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework.response import Response

from ..providers.errors import ProviderError
from ..services.analysis import AnalysisInputError

log = logging.getLogger(__name__)


def err(code: str, message: str, http: int, details=None) -> Response:
    return Response({"error": {"code": code, "message": message, "details": details}}, status=http)


def exception_handler(exc, context):
    if isinstance(exc, ValidationError):
        return err("invalid_request", "The request is invalid.", 400, exc.detail)
    if isinstance(exc, AnalysisInputError):
        return err("invalid_request", str(exc), 400)
    if isinstance(exc, ProviderError):
        return err(exc.code, exc.message, exc.http_status)
    if isinstance(exc, RequestDataTooBig):
        return err("payload_too_large", "Request body is too large.", 413)
    if isinstance(exc, Throttled):
        wait = getattr(exc, "wait", None)
        response = err("rate_limited", "Too many requests. Please slow down.", 429)
        if wait is not None:
            response["Retry-After"] = str(int(wait) + 1)
        return response
    status_code = getattr(exc, "status_code", None)
    if status_code and 400 <= status_code < 500:
        return err("bad_request", str(getattr(exc, "detail", "Bad request")), status_code)
    log.exception("Unhandled error")  # stack trace goes to logs only, never to the client
    return err("internal_error", "An unexpected error occurred.", status.HTTP_500_INTERNAL_SERVER_ERROR)
