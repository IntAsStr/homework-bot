class HomeWorkBotError(Exception):
    """Базовый класс для всех исключений бота."""
    pass


class APIRequestError(HomeWorkBotError):
    """Ошибка запроса к API Практикума."""
    pass
