
class ApiStatusCodeError(Exception):
    """Исключение для проверки статуса в ответе API."""

    pass


class UndocumentedStatusError(Exception):
    """Недокументированный статус."""

    pass


class RequestError(Exception):
    """Ошибка запроса."""

    pass


class SendMessageError(Exception):
    """Исключение для проверки отправки сообщений."""

    pass
