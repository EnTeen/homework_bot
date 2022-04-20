import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
CHECK_TIME = 2592000

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}

logging.basicConfig(
    handlers=[logging.StreamHandler()],
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s',
)

error_sent_messages = []


class APIAnswerError(Exception):
    """Кастомная ошибка API."""

    pass


def send_message(bot, message):
    """Отправляет сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'Удачная отправка сообщения: "{message}"')
    except telegram.error.NetworkError(message):
        logging.error(f'Сбой при отправке сообщения: {message}')


def get_api_answer(current_timestamp):
    """Отправляет запрос к API."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise Exception('ENDPOINT не отвечает')
    except requests.exceptions.RequestException as error:
        logging.error("OOps: Something Else", error)
    except requests.exceptions.HTTPError as error:
        logging.error("Ошибка Http:", error)
    except requests.exceptions.ConnectionError as error:
        logging.error("Ошибка подключения:", error)
    except requests.exceptions.Timeout as error:
        logging.error("Время подключения вышло:", error)
    except Exception:
        raise APIAnswerError('Ошибка API')
    return response.json()


def check_response(response):
    """Проверяет коректность полученного ответа."""
    if not isinstance(response, dict):
        raise TypeError('Полученный ответ не словарь')
    if not response['homeworks']:
        raise IndexError('В ответе нет домашней работы')
    try:
        homework = response.get('homeworks')
    except Exception as error:
        logging.error(f'Ошибка в фомирвоании списка homeworks: {error}')
    if not isinstance(homework, list):
        raise TypeError('Ответ не в виде списка:')
    return homework


def parse_status(homework):
    """Подготовка ответа."""
    keys = ('status', 'homework_name')
    for key in keys:
        if key not in homework:
            raise KeyError(f'{key} нет в ответе')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Статус домашней работы не определен')
    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    vars = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    return None not in vars


def log_and_inform(bot, message):
    """Обработка ошибки  ERROR. Отправляет уведомление."""
    logging.error(message)
    if message not in error_sent_messages:
        try:
            send_message(bot, message)
            error_sent_messages.append(message)
        except Exception as error:
            logging.info('Сбой отправки сообщения об ошибке, '
                         f'{error}')


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    status = ''
    check_result = check_tokens()
    if not check_result:
        message = 'Не доступны переменные окружения'
        logging.critical(message)
        raise SystemExit(message)

    while True:
        try:
            current_timestamp = int(time.time()) - CHECK_TIME
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            message = parse_status(homework)
            if message != status:
                send_message(bot, message)
                status = message
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != status:
                send_message(bot, message)
                status = message
            logging.error(error, exc_info=True)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
