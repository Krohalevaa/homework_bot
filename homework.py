import logging
import os
import datetime
import json
import time
import requests
import telegram

from telebot import TeleBot, types
from dotenv import load_dotenv

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
    level=logging.DEBUG,
    filename="bot.log",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())

class TheAnswerIsNot200Error(Exception):
    """Ответ сервера не равен 200."""

class EmptyDictionaryOrListError(Exception):
    """Пустой словарь или список."""


class UndocumentedStatusError(Exception):
    """Недокументированный статус."""


class RequestExceptionError(Exception):
    """Ошибка запроса."""


def check_tokens():
    """Проверяет доступность переменных окружения."""
    no_tokens_msg = (
        "Выполнение программы остановлено. "
        "Проверьте наличие всех переменных окружения:"
    )
    tokens_bool = True
    if PRACTICUM_TOKEN is None:
        tokens_bool = False
        logger.critical(f"{no_tokens_msg} PRACTICUM_TOKEN")
    if TELEGRAM_TOKEN is None:
        tokens_bool = False
        logger.critical(f"{no_tokens_msg} TELEGRAM_TOKEN")
    if TELEGRAM_CHAT_ID is None:
        tokens_bool = False
        logger.critical(f"{no_tokens_msg} CHAT_ID")
    return tokens_bool


def send_message(bot, message):
    """
    Отправляет сообщение в Telegram-чат,
    определяемый переменной окружения TELEGRAM_CHAT_ID.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f"Сообщение в Telegram успешно отправлено: {message}")
    except telegram.error.BadRequest as telegram_error:
        logger.error(f"Сообщение в Telegram не отправлено: {telegram_error}")


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    headers = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}
    payload = {"from_date": timestamp}
    try:
        response = requests.get(ENDPOINT, headers=headers, params=payload)
        if response.status_code != 200:
            code_api_msg = (
                f"Эндпоинт {ENDPOINT} недоступен."
                f" Код ответа API: {response.status_code}"
            )
            logger.error(code_api_msg)
            raise TheAnswerIsNot200Error(code_api_msg)
        return response.json()
    except requests.exceptions.RequestException as request_error:
        code_api_msg = f"Код ответа API (RequestException): {request_error}"
        logger.error(code_api_msg)
    except json.JSONDecodeError as format_error:
        code_api_msg = f"Код ответа API (ValueError): {format_error}"
        logger.error(code_api_msg)


def check_response(response):
    """
    Проверяет ответ API на соответствие документации
    из урока «API сервиса Практикум Домашка».
    """
    status = response["homeworks"][0].get("status")
    if response.get("homeworks") is None:
        code_api_msg = "Отсутствие ожидаемых ключей" "в ответе API"
        logger.error(code_api_msg)
    if status not in HOMEWORK_VERDICTS:
        code_api_msg = (
            "Ошибка неожиданный статус,"
            f"обнаруженный в ответе API: {status}"
        )
        logger.error(code_api_msg)
    return response["homeworks"][0]


def parse_status(homework):
    """
    Извлекает из информации о конкретной домашней работе
    статус этой работы.
    """
    status = homework.get("status")
    homework_name = homework.get("homework_name")
    if status is None:
        code_api_msg = "Ошибка пустое значение статуса"
        logger.error(code_api_msg)
        raise UndocumentedStatusError(code_api_msg)
    verdict = HOMEWORK_VERDICTS[status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""

    if not check_tokens():
        exit()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    now = datetime.datetime.now()
    send_message(bot, f'Я начал свою работу: {now.strftime("%d-%m-%Y %H:%M")}')
    tmp_status = "reviewing"
    errors = True
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework and tmp_status != homework["status"]:
                message = parse_status(homework)
                send_message(bot, message)
                tmp_status = homework["status"]
            logger.info("Изменений нет, ждем 10 минут и проверяем API")
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            if errors:
                errors = False
                send_message(bot, message)
            logger.critical(message)
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()

