class ProviderError(Exception):
    code = "provider_error"
    http_status = 502

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ProviderConfigError(ProviderError):
    code, http_status = "provider_not_configured", 503


class ProviderTimeout(ProviderError):
    code, http_status = "provider_timeout", 504


class ProviderUnavailable(ProviderError):
    code = "provider_unavailable"


class ProviderResponseError(ProviderError):
    code = "provider_bad_response"


class NoRouteError(ProviderError):
    code, http_status = "no_route", 404
