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

load_dotenv()
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(stream=sys.stdout))


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID
    }
    missing_tokens = [
        token_name for token_name,
        token_value in tokens.items() if not token_value]
    if missing_tokens:
        return False, missing_tokens
    return True, tokens


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f"Ура! Это сообщение успешно отправлено: {message}")
    except (ApiException, requests.RequestException) as error:
        logging.error(
            f"Ужас! Это сообщение: {message}"
            f"отправить не получилось: {error}")


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту.API-сервиса Практикум.Домашка."""
    params = {"from_date": timestamp}
    logging.info(f"Отправка запроса на {ENDPOINT} с параметрами {params}")
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        logging.error(error)
        raise EndpointError(f"Ошибка запроса к API: {error}")
    if response.status_code != HTTPStatus.OK:
        endpoint_message = (
            f'Ответ с адреса: {response.url} не соответствует ожидаемому.'
            f'Код ответа: {response.status_code}]'
        )
        raise EndpointError(endpoint_message)
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not response:
        raise KeyError("Ответ API пуст.")

    if not isinstance(response, dict):
        raise TypeError("Ответ API должен быть словарем.")

    if "homeworks" not in response:
        raise KeyError("Ключ 'homeworks' отсутствует в ответе API.")

    if not isinstance(response['homeworks'], list):
        raise TypeError("Значение ключа 'homeworks' должно быть списком.")

    return response.get("homeworks")


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if not homework:
        raise KeyError('Переменная имеет значение False.')

    if "status" not in homework:
        raise StatusError("Нет статуса.")
    hw_status = homework.get("status")
    hw_verdict = HOMEWORK_VERDICTS.get(hw_status)

    if "homework_name" not in homework:
        raise KeyError("Ключ 'homework_name' отсутствует в ответе.")
    homework_name = homework["homework_name"]

    if hw_status not in HOMEWORK_VERDICTS:
        raise KeyError(f"Статус домашней работы: {hw_status} неизвестен.")
    return f'Изменился статус проверки работы "{homework_name}". {hw_verdict}'


def main():
    """Основная логика работы бота."""
    tokens_ok, result = check_tokens()
    if not tokens_ok:
        missing_tokens = ", ".join(result)
        logger.critical(
            f"Программа остановлена, отсутствуют токены: {missing_tokens}"
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
                for homework in homeworks:
                    message = parse_status(homework)
                    if last_message != message:
                        send_message(bot, message)
                        last_message = message
                    else:
                        logger.debug("Сообщение не отправлено: дублирование.")
            else:
                logging.debug("Все по прежнему, изменений нет.")
            timestamp = response.get("timestamp", timestamp)
        except (KeyError, TypeError) as error:
            key_type_e_msg = f"Ошибка: {type(error).__name__}: {error}"
            logging.error(key_type_e_msg)
            send_message(bot, key_type_e_msg)
        except Exception as error:
            e_msg = f"Ошибка в работе программы: {error}"
            logging.error(e_msg)
            send_message(bot, e_msg)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        filename="tg_bot.log",
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",)
    main()
