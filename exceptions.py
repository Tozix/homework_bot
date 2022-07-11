class UndocumentedStatusError(Exception):
    """Недокументированный статус."""

    pass


class RequestError(Exception):
    """Ошибка запроса."""

    pass


class EndPointError(Exception):
    """Ошибка Endpoint."""

    pass


class ListEmptyError(Exception):
    """Список работ пуст."""

    pass


class DictEmptyError(Exception):
    """Словарь пуст."""

    pass


class SendMessageError(Exception):
    """Исключение для проверки отправки сообщений."""

    pass
