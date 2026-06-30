import logging
import os
import sys
import time

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
    'Эндпоинт {url} недоступен. Headers: {headers}, '
    'params: {params}. Код ответа API: {code}'
)
STATUS_CHANGED_MESSAGE = 'Изменился статус проверки работы "{name}". {verdict}'


def configure_logging():
    """Настраивает логирование."""
    log_dir = os.path.join(os.path.expanduser('~'), 'homework_bot_logs')
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f'{os.path.basename(__file__)}.log')

    logging.basicConfig(
        format='%(asctime)s %(name)s %(funcName)s:%(lineno)d '
        '[%(levelname)s] %(message)s',
        level=logging.DEBUG,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding='utf-8'),
        ],
    )


REQUIRED_TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')


def check_tokens() -> bool:
    """Проверяет наличие всех необходимых переменных окружения."""
    missing_tokens = [
        name for name in REQUIRED_TOKENS if not globals().get(name)
    ]
    if missing_tokens:
        logging.critical(TOKEN_MISSING_MESSAGE.format(tokens=missing_tokens))
    return not missing_tokens


def send_message(bot, message) -> bool:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        logging.exception(f'Ошибка при отправке сообщения {message}: {e}.')
        return False
    logging.debug(f'Сообщение {message} успешно отправлено!')
    return True


def get_api_answer(timestamp: int) -> dict:
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as e:
        raise ConnectionError(
            f'Эндпоинт {ENDPOINT} недоступен. '
            f'headers={HEADERS}, params={params}. Ошибка: {e}'
        )

    if response.status_code != requests.codes.ok:
        raise UnavailableEndpointError(
            ENDPOINT_ERROR_MESSAGE.format(
                url=ENDPOINT,
                headers=HEADERS,
                params=params,
                code=response.status_code,
            )
        )
    response_json = response.json()
    for key in ('error', 'code'):
        if key in response_json:
            raise UnavailableEndpointError(
                ENDPOINT_ERROR_MESSAGE.format(
                    url=ENDPOINT,
                    headers=HEADERS,
                    params=params,
                    code=response.status_code,
                )
            )
    return response_json


def check_response(response) -> list:  # -> list[Any]:
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем.')
    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ "homeworks".')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError(
            f'Значение ключа "homeworks" не является списком: '
            f'{type(response.get('homeworks'))}'
        )
    if not isinstance(response.get('current_date'), int):
        raise TypeError(
            f'Значение ключа "current_date" не является int: '
            f'{type(response.get('current_date'))}'
        )
    return response['homeworks']


def parse_status(homework) -> str:
    """Извлекает статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе API отсутствует ключ "homework_name"')
    if 'status' not in homework:
        raise KeyError('В ответе API отсутствует ключ "status"')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'В ответе API отсутствует допустимое значение: {status}'
        )

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
                status: str = parse_status(homeworks[-1])
                if send_message(bot, status):
                    logging.debug(
                        f'Статус домашней работы успешно отправлен: {status}'
                    )
                    timestamp = response.get('current_date', timestamp)
            else:
                logging.debug('Нет новых статусов домашних работ.')
        except Exception as e:
            message: str = f'Сбой в работе программы: {e}'
            logging.error(message)
            if last_error_message != message and send_message(bot, message):
                last_error_message: str = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    configure_logging()
    main()
