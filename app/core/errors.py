class CreatorDatasetError(Exception):
    """Base application error."""


class AuthenticationRequired(CreatorDatasetError):
    """Authentication is required before the platform can be queried."""


class PlatformBlocked(CreatorDatasetError):
    """The platform blocked or challenged the current session."""


class IntegrationNotInstalled(CreatorDatasetError):
    """An optional platform integration is not installed."""


class PlatformRequestError(CreatorDatasetError):
    """A platform request failed."""
