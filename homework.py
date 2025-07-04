import logging
import os
import requests
import time

from dotenv import load_dotenv
from telebot import TeleBot, types

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='homework_bot.log',
    handlers=[
        logging.StreamHandler()
    ]
)

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


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if not PRACTICUM_TOKEN:
        return False
    if not TELEGRAM_TOKEN:
        return False
    if not TELEGRAM_CHAT_ID:
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправленно')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Делает запрос к API Практикума."""
    try:
        params = {'from_date': timestamp}
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
        )
        if response.status_code != 200:
            raise requests.RequestException

    except requests.RequestException:
        raise requests.RequestException(
            f"API вернул код {response.status_code}. URL: {ENDPOINT}"
        )
    except ValueError:
        logging.error(
            f"API вернул код {response.status_code}. URL: {ENDPOINT}"
        )

    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    try:
        if not isinstance(response, dict):
            raise TypeError('Ответ API не является словарем')

        if 'homeworks' not in response:
            raise KeyError('Ключ "homeworks" отсутствует в ответе API')

        homeworks = response['homeworks']
        if not isinstance(homeworks, list):
            raise TypeError('Данные в ключе "homeworks" не являются списком')

    except TypeError:
        logging.error('Ошибка типа данных')
        raise
    except KeyError:
        logging.error('Ошибка отсутствия ключа')
        raise
    except Exception:
        logging.error('Неожиданная ошибка')
        raise
    return homeworks


def parse_status(homework):
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


def main():
    """Основная логика работы бота."""

    if not check_tokens():
        logging.critical('Отсутствуют обязательные переменные окружения')
        exit(1)

    bot = TeleBot(token=TELEGRAM_TOKEN)
    logging.info('Бот запущен')
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                logging.debug('Сообщение отправленно')
            else:
                logging.debug('Нет новых статусов')

            timestamp = response.get('current_date', timestamp)
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
