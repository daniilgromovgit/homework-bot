import os
import logging
import requests

from dotenv import load_dotenv
from telebot import TeleBot


load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}

logging.basicConfig(
    format='%(asctime)s %(name)s [%(levelname)s] %(message)s',
    level=logging.INFO,
)

bot = TeleBot(token=TELEGRAM_TOKEN)
bot.send_message(chat_id=TELEGRAM_CHAT_ID, text='Спасибо, что включили меня')
def check_tokens():
    required_tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing = [name for name, token in required_tokens.items() if not token]
    for name in missing:
        logging.critical(f'Отсутствует обязательная переменная окружения: {name}.')
    return not missing

def send_message(bot, message) -> bool:
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        logging.error(f'Ошибка при отправке сообщения: {e}.')
        return False
    logging.debug(f'Сообщение успешно отправлено!')
    return True


def get_api_answer(timestamp):# -> Any:
    try:
        homework_statuses: requests.Response = requests.get(ENDPOINT, headers=HEADERS, params={'from_date': timestamp})
    except Exception as e:
        logging.error(f'Эндпоинт недоступен: {e}.')
    return homework_statuses.json()


def check_response(response):


def parse_status(homework):
    ...

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""

    ...

    # Создаем объект класса бота
    bot = ...
    timestamp = int(time.time())

    ...

    while True:
        try:
            ...

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            ...
        ...


if __name__ == "__main__":
    main()
