
class ApiStatusCodeException(Exception):
    """Исключение для проверки статуса в ответе API."""
    pass


class UndocumentedStatusError(Exception):
    """Недокументированный статус."""
    pass


class RequestExceptionError(Exception):
    """Ошибка запроса."""
    pass


class SendMessageException(Exception):
    """Исключение для проверки отправки сообщений."""
    pass
