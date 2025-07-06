class HomeWorkBotError(Exception):
    """Базовый класс для всех исключений бота."""


class APIRequestError(HomeWorkBotError):
    """Ошибка запроса к API Практикума."""
