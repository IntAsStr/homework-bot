import logging
import os
import time
from typing import Any, Dict, List

import requests
import telebot
from dotenv import load_dotenv
from telebot import TeleBot
from logging import StreamHandler

from exceptions import APIRequestError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('YANDEX_MY_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_MY_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> List[str]:
    """Проверяет доступность переменных окружения."""
    missing_tokens = []

    if not PRACTICUM_TOKEN:
        missing_tokens.append('PRACTICUM_TOKEN')
    if not TELEGRAM_TOKEN:
        missing_tokens.append('TELEGRAM_TOKEN')
    if not TELEGRAM_CHAT_ID:
        missing_tokens.append('TELEGRAM_CHAT_ID')

    return missing_tokens


def send_message(bot: TeleBot, message: str) -> None:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправлено')
    except (requests.RequestException,
            telebot.apihelper.ApiTelegramException, Exception
            ) as error:
        error_type = 'Неизвестная ошибка'
        if isinstance(error, requests.RequestException):
            error_type = 'Сетевая ошибка'
        elif isinstance(error, telebot.apihelper.ApiTelegramException):
            error_type = 'Ошибка телеграмм API'
        logging.error(f'{error_type} при отправке сообщения {error}')


def get_api_answer(timestamp: int) -> dict[str, Any]:
    """Делает запрос к API Практикума."""
    params = {'from_date': timestamp}
    logging.info(f"Отправка запроса к API. URL: {ENDPOINT}, ")
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )

    except (requests.RequestException, ValueError) as error:
        if isinstance(error, requests.RequestException):
            error_type = 'Сетевая ошибка'
        elif isinstance(error, ValueError):
            error_type = 'Ошибка в значении'
        logging.error(f'{error_type} при запросе к API {error}')

    if response.status_code != 200:
        raise APIRequestError(
            f"API вернул код {response.status_code}. URL: {ENDPOINT}"
        )

    return response.json()


def check_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарём')

    if 'homeworks' not in response:
        raise KeyError('Отсутствует обязательный ключ "homeworks"')

    homeworks = response['homeworks']

    if not isinstance(homeworks, list):
        raise TypeError('Данные в "homeworks" должны быть списком')

    return homeworks


def parse_status(homework: Dict[str, Any]) -> str:
    """Извлекает статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе API домашки нет ключа `homework_name`')
    if 'status' not in homework:
        raise KeyError('В ответе API домашки нет ключа `status`')

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы: {status}')
    verdict = HOMEWORK_VERDICTS[status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    missing_tokens = check_tokens()
    if missing_tokens:
        logging.critical(
            f'Отсутствует обязательные переменные окружения: {missing_tokens}'
        )
        exit(1)

    bot = TeleBot(token=TELEGRAM_TOKEN)
    logging.info('Бот запущен')
    timestamp = int(time.time())
    last_sent_message: str | None = None
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = "Нет новых статусов - работы не проверены"

            if message != last_sent_message:
                send_message(bot, message)
                last_sent_message = message
                logging.debug('Сообщение отправлено')
                timestamp = response.get('current_date', timestamp)

        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            if error_message != last_sent_message:
                logging.error(error_message)
                send_message(bot, error_message)
                last_sent_message = error_message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='homework_bot.log',
        filemode='w',
    )

    logger = logging.getLogger(__name__)
    handler = StreamHandler()
    logger.addHandler(handler)
    main()
