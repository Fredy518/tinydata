"""tinydata exception hierarchy."""


class TinyDataError(Exception):
    """Base class for tinydata errors."""


class TinyDataDependencyError(TinyDataError):
    """Required optional dependency is missing."""


class TinyDataConfigError(TinyDataError):
    """Configuration is invalid or incomplete."""


class TinyDataAuthError(TinyDataError):
    """Tinysoft authentication failed."""


class TinyDataTimeoutError(TinyDataError):
    """Tinysoft call exceeded the configured timeout."""


class TinyDataQueryError(TinyDataError):
    """Tinysoft query failed."""


class TinyDataRateLimitError(TinyDataQueryError):
    """Tinysoft rejected the request because OPI concurrency or request limits were exceeded."""


class TinyDataCodePoolError(TinyDataError):
    """A dataset needs codes but no valid code pool was available."""


class TinyDataParameterError(TinyDataError):
    """A public API call is missing required query-safety parameters."""
