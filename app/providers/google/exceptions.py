"""Exceptions raised by the Google provider layer."""


class GoogleError(Exception):
    """Base class for every Google integration failure."""


class GoogleNotConfigured(GoogleError):
    """GOOGLE_CLIENT_ID / SECRET / REDIRECT_URI are missing."""


class GoogleNotConnected(GoogleError):
    """The user has not connected the requested Google service."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(
            f"Google service '{service_name}' is not connected."
        )


class GoogleReauthRequired(GoogleError):
    """The stored grant is no longer usable and the user must re-consent."""

    def __init__(self, service_name: str, reason: str = ""):
        self.service_name = service_name
        self.reason = reason
        super().__init__(
            f"Google service '{service_name}' needs to be reconnected."
            + (f" ({reason})" if reason else "")
        )


class GoogleUnauthorized(GoogleError):
    """A Google API call returned 401 for the supplied access token."""


class GoogleRateLimited(GoogleError):
    """Google throttled the request and retries were exhausted."""


class GoogleNotFound(GoogleError):
    """The requested Google resource does not exist or is not visible."""


class GoogleAPIError(GoogleError):
    """Any other non-successful Google API response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Google API error {status_code}: {message}")
