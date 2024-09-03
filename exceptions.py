class EndpointError(Exception):
    """Ошибка в адресе."""

    def __init__(self, response):
        """Обозначение ошибки."""
        message = (
            f'Endpoint {response.url} not available. '
            f'API response code: {response.status_code}]'
        )
        super().__init__(message)


class HavingStatusError(Exception):
    """Неправильный статус."""

    def __init__(self, text):
        """Обозначение ошибки."""
        message = (
            f'Parsing the API response: {text}'
        )
        super().__init__(message)


class ResponseFormatError(Exception):
    """Ошибка формата."""

    def __init__(self, text):
        """Обозначение ошибки."""
        message = (
            f'API response check: {text}'
        )
        super().__init__(message)
