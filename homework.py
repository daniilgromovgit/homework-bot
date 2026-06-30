import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telebot import TeleBot

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

logging.basicConfig(
    format='%(asctime)s %(name)s [%(levelname)s] %(message)s',
    level=logging.DEBUG,
)


def check_tokens() -> bool:
    """Проверяет наличие всех необходимых переменных окружения."""
    required_tokens: dict[str, str | None] = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    missing_tokens: list[str] = [
        name for name, token in required_tokens.items() if not token
    ]
    for name in missing_tokens:
        logging.critical(
            f'Отсутствует обязательная переменная окружения: {name}.'
        )
    return not missing_tokens


def send_message(bot, message) -> bool:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        logging.error(f'Ошибка при отправке сообщения: {e}.')
        return False
    logging.debug('Сообщение успешно отправлено!')
    return True


def get_api_answer(timestamp: int) -> dict:
    """Делает запрос к единственному эндпоинту API-сервиса."""
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
    except requests.RequestException as e:
        raise ConnectionError(f'Эндпоинт {ENDPOINT} недоступен: {e}')

    if homework_statuses.status_code != 200:
        raise requests.HTTPError(
            f'Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {homework_statuses.status_code}'
        )
    return homework_statuses.json()


def check_response(response) -> list:  # -> list[Any]:
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем.')
    if 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ "homeworks".')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Значение ключа "homeworks" не является списком.')
    if not isinstance(response['current_date'], int):
        raise TypeError('Значение ключа "current_date" не является int')
    return response['homeworks']


def parse_status(homework) -> str:
    """Извлекает статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе API отсутствует ключ "homework_name"')
    if 'status' not in homework:
        raise KeyError('В ответе API отсутствует ключ "status"')
    if homework['status'] not in HOMEWORK_VERDICTS:
        raise ValueError('В ответе API отсутствует допустимое значение')
    homework_name: str = homework['homework_name']
    verdict: str = HOMEWORK_VERDICTS[homework['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit(
            'Отсутствуют обязательные переменные окружения.'
            'Программа принудительно остановлена.'
        )
    assert TELEGRAM_TOKEN is not None
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = ''
    while True:
        try:
            response: dict = get_api_answer(timestamp)
            homeworks: list = check_response(response)
            if homeworks:
                for homework in homeworks:
                    status: str = parse_status(homework)
                    send_message(bot, status)
            else:
                logging.debug('Нет новых статусов домашних работ.')
            timestamp: int = response['current_date']
        except Exception as e:
            message: str = f'Сбой в работе программы: {e}'
            logging.error(message)
            if last_error_message != message:
                if send_message(bot, message):
                    last_error_message: str = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
