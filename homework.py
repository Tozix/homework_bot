import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from requests.exceptions import RequestException
from telegram import Bot

from exceptions import (ApiStatusCodeError, RequestError, SendMessageError,
                        UndocumentedStatusError)

load_dotenv()

PRACTICUM_TOKEN: Optional[str] = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: Optional[str] = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: Optional[str] = os.getenv('TELEGRAM_CHAT_ID')


logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s %(name)s',
    filename='main.log', filemode='w',
    level=logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


file_log_handler = RotatingFileHandler(
    filename='bot.log',
    encoding='utf8',
    maxBytes=50000000,
    backupCount=5
)
console_out_handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
)
file_log_handler.setFormatter(formatter)
console_out_handler.setFormatter(formatter)
logger.addHandler(file_log_handler)
logger.addHandler(console_out_handler)

RETRY_TIME: int = 600
SECONDS_MESSAGE_TIMEOUT: int = 10
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: Dict[str, str] = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES: Dict[str, str] = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> bool:
    """
    Проверяет доступность переменных окружения,
    которые необходимы для работы программы.
    Если отсутствует хотя бы одна переменная окружения —
    функция должна вернуть False, иначе — True.
    """
    var_list = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN',
                'TELEGRAM_CHAT_ID']
    result = True
    for name in var_list:
        if eval(name) is None:
            result = False
            logger.critical(
                f'Отсутствует обязательная переменная окружения: {name}')
    return result


def get_api_answer(current_timestamp: int) -> dict:
    """
    Делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    timestamp: Optional[int] = current_timestamp or int(time.time())
    params: Dict[str, Optional[int]] = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except RequestException as error:
        logger.error(f'Ошибка при запросе к основному API: {error}')
        raise RequestError(
            f'Ошибка при запросе к основному API: {error}')
    if response.status_code != HTTPStatus.OK:
        logger.error(f'Ошибка! Код ответа API: {response.status_code}')
        raise ApiStatusCodeError(
            f'Ошибка! Код ответа API: {response.status_code}')
    try:
        return response.json()
    except ValueError:
        logger.error('Ошибка парсинга ответа из формата json')
        raise ValueError('Ошибка парсинга ответа из формата json')


def check_response(response: Dict[str, List[dict]]) -> list:
    """
    Проверяет ответ API на корректность.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ (он может быть и пустым),
    доступный в ответе API по ключу 'homeworks'.
    """
    if type(response) is not dict:
        raise TypeError('Ответ API отличен от словаря')
    try:
        list_homeworks = response['homeworks']
    except KeyError:
        raise KeyError('Ошибка словаря по ключу homeworks')
    if type(list_homeworks) is not list:
        raise TypeError(
            'Оттвет от API под ключом `homeworks`'
            + ' домашки приходят не в виде списка'
        )
    return list_homeworks


def parse_status(homework: Dict[str, str]) -> str:
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.
    В качестве параметра функция получает только один элемент из списка
    домашних работ. В случае успеха, функция возвращает подготовленную
    для отправки в Telegram строку,
    содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')
    if homework_status not in HOMEWORK_STATUSES:
        raise UndocumentedStatusError(
            'Недокументированный статус домашней работы,'
            + f'обнаруженный в ответе API: {homework_status}')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    logger.info(f'Статус работы: {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message: str) -> None:
    """
    Отправляет сообщение в Telegram чат, определяемый переменной
    окружения TELEGRAM_CHAT_ID.
    Принимает на вход два параметра:
    экземпляр класса Bot и строку с текстом сообщения.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения: {error}')
        raise SendMessageError(error)
    else:
        logger.info(f'Бот отправил сообщение: {message}')


def main() -> None:
    """Основная логика работы бота."""
    if not check_tokens:
        print('Программа принудительно остановлена.')
        os._exit(1)
    bot = Bot(token=str(TELEGRAM_TOKEN))
    error_message: str = ''
    message: str = ''
    while True:
        try:
            current_timestamp: int = int(time.time())
            response = get_api_answer(current_timestamp)
            list_homeworks = check_response(response)
            if len(list_homeworks) > 0:
                logger.info(f'Найдено {len(list_homeworks)} работ')
                for homework in list_homeworks:
                    send_message(bot, parse_status(homework))
                    time.sleep(SECONDS_MESSAGE_TIMEOUT)
            else:
                logger.debug('Отсутствие в ответе новых статусов')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if error_message != message:
                send_message(bot, message)
                error_message = message
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
