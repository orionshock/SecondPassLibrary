class SessionClosedError(Exception):
    pass


class BookAccessRequiredError(Exception):
    pass


class FinalizationWithoutActiveSessionError(Exception):
    pass


class IdempotencyConflictError(Exception):
    pass


class IdempotencyInProgressError(Exception):
    pass
