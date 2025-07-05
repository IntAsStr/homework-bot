import logging
import os
import requests
import time
import telebot
from typing import List, Dict, Any

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
    except requests.RequestException as error:
        logging.error(f'Сетевая ошибка при отправке сообщения: {error}')
    except telebot.apihelper.ApiTelegramException as error:
        logging.error(f'Ошибка Telegram API: {error}')
    except Exception as error:
        logging.error(f'Неожиданная ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp: int) -> dict[str, Any]:
    """Делает запрос к API Практикума."""
    try:
        params = {'from_date': timestamp}
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )
        if response.status_code != 200:
            raise APIRequestError(
                f'API вернул код {response.status_code}.'
            )

    except requests.RequestException:
        raise requests.RequestException(
            f"API вернул код {response.status_code}. URL: {ENDPOINT}"
        )
    except ValueError:
        logging.error(
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
    try:
        if 'homework_name' not in homework:
            raise KeyError('В ответе API домашки нет ключа `homework_name`')
        if 'status' not in homework:
            raise KeyError('В ответе API домашки нет ключа `status`')

        homework_name = homework['homework_name']
        status = homework['status']

        if status not in HOMEWORK_VERDICTS:
            raise ValueError(f'Неизвестный статус работы: {status}')
        verdict = HOMEWORK_VERDICTS[status]

    except ValueError:
        logging.error(
            f'Неизвестный статус работы: {status}'
            f'Или в ответе API домашки нет ключа `homework_name`'
        )
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    missing_tokens = check_tokens()
    if missing_tokens:
        for item in missing_tokens:
            logging.critical(
                f'Отсутствует обязательная переменная окружения: {item}'
            )
        exit(1)

    bot = TeleBot(token=TELEGRAM_TOKEN)
    logging.info('Бот запущен')
    timestamp = int(time.time())
    last_sent_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
                if message != last_sent_message:
                    send_message(bot, message)
                    last_sent_message = message
                    logging.debug('Сообщение отправлено')
            else:
                no_changes_message = "Нет новых статусов - работы не проверены"
                if no_changes_message != last_sent_message:
                    send_message(bot, no_changes_message)
                    last_sent_message = no_changes_message
                    logging.debug('Сообщение отсутствия изменений отправлено')

            timestamp = response.get('current_date', timestamp)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            try:
                send_message(bot, message)
            except Exception:
                pass  # Игнорируем ошибки при отправке уведомлений об ошибках
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
