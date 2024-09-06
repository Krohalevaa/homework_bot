import logging
import sys
import time
import requests
import os
from http import HTTPStatus
from telebot.apihelper import ApiException

from exeptions import EndpointError, StatusError
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
    level=logging.DEBUG,
    filename="tg_bot.log",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens_message = (
        "Программа остановлена, отсутствуют необходимые токены. "
    )
    tokens_bool = True
    if PRACTICUM_TOKEN is None:
        tokens_bool = False
        logger.critical(f"{tokens_message} PRACTICUM_TOKEN")
    if TELEGRAM_TOKEN is None:
        tokens_bool = False
        logger.critical(f"{tokens_message} TELEGRAM_TOKEN")
    if TELEGRAM_CHAT_ID is None:
        tokens_bool = False
        logger.critical(f"{tokens_message} TELEGRAM_CHAT_ID")
    return tokens_bool


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f"Ура! Это сообщение успешно отправлено: {message}")
    except ApiException as api_error:
        logging.error(
            f"Ужас! Это сообщение: {message}"
            f"отправить не получилось: {api_error}")
    except requests.RequestException as request_error:
        logging.error(
            f"Ужас! Это сообщение: {message}"
            f"отправить не получилось: {request_error}")


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту.API-сервиса Практикум.Домашка."""
    params = {"from_date": timestamp}
    logging.info(f"Отправка запроса на {ENDPOINT} с параметрами {params}")
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            endpoint_message = (
                f'Адрес: {response.url} не отвечает. '
                f'Код ответа: {response.status_code}]'
            )
            raise EndpointError(response, endpoint_message)
    except requests.RequestException as error:
        logging.error(error)
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not response:
        message = "Ваш ответ пуст."
        logging.error(message)
        raise KeyError(message)

    if not isinstance(response, dict):
        message = 'Ответ должен быть словарем.'
        logging.error(message)
        raise TypeError(message)

    if "homeworks" not in response:
        message = 'Нет ключа с таким названием.'
        logging.error(message)
        raise KeyError(message)

    if not isinstance(response['homeworks'], list):
        message = "Ответ должен быть списком."
        logging.error(message)
        raise TypeError(message)

    return response.get("homeworks")


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if "status" not in homework:
        message = "Нет статуса."
        logging.error(message)
        raise StatusError(message)
    hw_status = homework.get("status")
    hw_verdict = HOMEWORK_VERDICTS.get(hw_status)
    if not homework:
        message = 'Нет ключа с таким названием.'
        logging.error(message)
        raise KeyError(message)
    if homework.get("homework_name"):
        homework_name = homework.get("homework_name")
    else:
        homework_name = "XXX"
        logging.warning(f"Такого имени: {homework} нет в ответе")
        raise KeyError(homework_name)

    if hw_status not in HOMEWORK_VERDICTS:
        message = "Статус домашней работы неизвестен."
        logging.error(message)
        raise KeyError(message)
    return f'Изменился статус проверки работы "{homework_name}". {hw_verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical(
            "Принудительная остановка программы из за отсутствия токенов."
        )
        sys.exit(1)
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    send_message(bot, "Привет! Я готов отслеживать изменения.")
    last_message = ""

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                logging.debug("Все по прежнему, изменений нет.")
            for homework in homeworks:
                message = parse_status(homework)
                if last_message != message:
                    send_message(bot, message)
                    last_message = message
            timestamp = response.get("timestamp")

        except Exception as error:
            if last_message != message:
                message = f"Ошибка в работе программы: {error}"
                send_message(bot, message)
                last_message = message
            else:
                last_message = ""
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        filename="tg_bot.log",
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.StreamHandler(stream=sys.stdout))
    main()
