import logging
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import UnavailableEndpointError

load_dotenv()

PRACTICUM_TOKEN: str | None = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: str | None = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: str | None = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: dict[str, str] = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS: dict[str, str] = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}
TOKEN_MISSING_MESSAGE = (
    'Отсутствуют обязательные переменные окружения: {tokens}'
)
ENDPOINT_ERROR_MESSAGE = (
    'Эндпоинт {url} недоступен. '
    'Headers: {headers}, params: {params}. Ошибка:{error}'
)
API_STATUS_ERROR_MESSAGE = (
    'Эндпоинт {url} вернул код {code} (headers={headers}, params={params}).'
)
API_ERROR_KEY_MESSAGE = (
    'API вернул ошибку по ключу "{key}": {value} '
    '(url={url}, headers={headers}, params={params}).'
)
STATUS_CHANGED_MESSAGE = 'Изменился статус проверки работы "{name}". {verdict}'
RESPONSE_TYPE_ERROR = (
    'Ответ API не является {type_name}. Получен тип: {actual_type}.'
)
KEY_TYPE_ERROR = (
    'Значение ключа "{key}" не является {type_name}. '
    'Получен тип: {actual_type}.'
)
KEY_MISSING_ERROR = 'В ответе API отсутствует ключ "{key}".'
VALUE_MISSING_ERROR = 'В ответе API отсутствует значение "{value}".'
DICT_TYPE = 'словарём'
LIST_TYPE = 'списком'
LOG_MESSAGE = 'Сообщение "{message}" {status}.'
MESSAGE_SENT = 'успешно отправлено'
MESSAGE_SEND_ERROR = 'не отправлено. Ошибка: {error}'
NO_NEW_STATUSES_MESSAGE = 'Нет новых статусов домашних работ.'
PROGRAMM_ERROR = 'Сбой в работе программы: {error}'

REQUIRED_TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')


def check_tokens() -> bool:
    """Проверяет наличие всех необходимых переменных окружения."""
    missing_tokens = [
        name for name in REQUIRED_TOKENS if not globals().get(name)
    ]
    if missing_tokens:
        logging.critical(TOKEN_MISSING_MESSAGE.format(tokens=missing_tokens))
    return not missing_tokens


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        logging.exception(
            LOG_MESSAGE.format(
                message=message, status=MESSAGE_SEND_ERROR.format(error=e)
            )
        )
        return False
    logging.debug(LOG_MESSAGE.format(message=message, status=MESSAGE_SENT))
    return True


def get_api_answer(timestamp: int) -> dict:
    """Делает запрос к единственному эндпоинту API-сервиса."""
    request_kwargs = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    try:
        response = requests.get(**request_kwargs)
    except requests.RequestException as e:
        raise ConnectionError(
            ENDPOINT_ERROR_MESSAGE.format(**request_kwargs, error=e)
        )

    if response.status_code != requests.codes.ok:
        raise UnavailableEndpointError(
            API_STATUS_ERROR_MESSAGE.format(
                **request_kwargs, code=response.status_code
            )
        )
    response_json = response.json()
    for key in ('error', 'code'):
        if key in response_json:
            raise UnavailableEndpointError(
                API_ERROR_KEY_MESSAGE.format(
                    **request_kwargs, key=key, value=response_json[key]
                )
            )
    return response_json


def check_response(response) -> list:  # -> list[Any]:
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(
            RESPONSE_TYPE_ERROR.format(
                type_name=DICT_TYPE, actual_type=type(response).__name__
            )
        )
    if 'homeworks' not in response:
        raise KeyError(KEY_MISSING_ERROR.format(key='homeworks'))
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            KEY_TYPE_ERROR.format(
                key='homeworks',
                type_name=LIST_TYPE,
                actual_type=type(homeworks).__name__,
            )
        )
    return homeworks


def parse_status(homework) -> str:
    """Извлекает статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError(KEY_MISSING_ERROR.format(key='homework_name'))
    if 'status' not in homework:
        raise KeyError(KEY_MISSING_ERROR.format(key='status'))
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(VALUE_MISSING_ERROR.format(value='status'))

    return STATUS_CHANGED_MESSAGE.format(
        name=homework['homework_name'],
        verdict=HOMEWORK_VERDICTS[status],
    )


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = ''
    while True:
        try:
            response: dict = get_api_answer(timestamp)
            homeworks: list = check_response(response)
            if homeworks:
                if send_message(bot, parse_status(homeworks[0])):
                    timestamp = response.get('current_date', timestamp)
            else:
                logging.debug(NO_NEW_STATUSES_MESSAGE)

        except Exception as e:
            message: str = PROGRAMM_ERROR.format(error=e)
            logging.error(message)
            if last_error_message != message and send_message(bot, message):
                last_error_message: str = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    log_file = Path(__file__).resolve().parent / f'{Path(__file__).name}.log'

    logging.basicConfig(
        format=(
            '%(asctime)s %(name)s %(funcName)s:%(lineno)d '
            '[%(levelname)s] %(message)s'
        ),
        level=logging.DEBUG,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding='utf-8'),
        ],
    )

    main()
