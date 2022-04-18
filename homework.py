import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from dotenv.main import logger

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
CHECK_TIME = 2592000

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s'
)

logger = logging.getLogger(__name__)

error_sent_messages = []


class APIAnswerError(Exception):
    """Кастомная ошибка API."""

    pass


def send_message(bot, message):
    """Отправляет сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Удачная отправка сообщения: "{message}"')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения: {error}')


def get_api_answer(current_timestamp):
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception:
        message = 'Ошибка API'
        raise APIAnswerError(message)
    try:
        if response.status_code != HTTPStatus.OK:
            message = 'ENDPOINT не отвечает'
            raise Exception(message)
    except Exception:
        message = 'Ошибка API'
        raise APIAnswerError(message)
    return response.json()


def check_response(response):
    """Проверяет коректность полученного ответа."""
    if not isinstance(response, dict):
        message = 'Полученный отвт не словарь'
        raise TypeError(message)
    if ['homeworks'][0] not in response:
        message = 'В ответе нет домашней работы'
        raise IndexError(message)
    homework = response.get('homeworks')[0]
    return homework


def parse_status(homework):
    """Подготовка ответа."""
    keys = ['status', 'homework_name']
    for key in keys:
        if key not in homework:
            message = f'{key} нет в ответе'
            raise KeyError(message)
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        message = 'Статус домашней работы не определен'
        raise KeyError(message)
    homework_name = homework['homework_name']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    vars = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return None not in vars


def log_and_inform(bot, message):
    """Обработка ошибки  ERROR. Отправляет уведомление."""
    logger.error(message)
    if message not in error_sent_messages:
        try:
            send_message(bot, message)
            error_sent_messages.append(message)
        except Exception as error:
            logger.info('Сбой отправки сообщения об ошибке, '
                        f'{error}')


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - CHECK_TIME
    check_result = check_tokens()
    if check_result is False:
        message = 'Не доступны переменные окружения'
        logger.critical(message)
        raise SystemExit(message)

    while True:
        try:
            response = get_api_answer(current_timestamp)
            if 'current_date' in response:
                current_timestamp = response['current_date']
            homework = check_response(response)
            if homework is not None:
                message = parse_status(homework)
                if message is not None:
                    send_message(bot, message)
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            log_and_inform(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
