import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from telegram import Bot

from exceptions import (DictEmptyError, EndPointError, ListEmptyError,
                        SendMessageError, UndocumentedStatusError)

load_dotenv()

PRACTICUM_TOKEN: Optional[str] = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: Optional[str] = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: Optional[str] = os.getenv('TELEGRAM_CHAT_ID')


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
    '%(asctime)s [%(levelname)s] %(message)s %(funcName)s %(lineno)s'
)
file_log_handler.setFormatter(formatter)
console_out_handler.setFormatter(formatter)
logger.addHandler(file_log_handler)
logger.addHandler(console_out_handler)

RETRY_TIME: int = 600
SECONDS_MESSAGE_TIMEOUT: int = 10
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: Dict[str, str] = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS: Dict[str, str] = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения.
    Которые необходимы для работы программы.
    Если отсутствует хотя бы одна переменная окружения —
    функция должна вернуть False, иначе — True.
    """
    logger.debug(
        'Проверяем доступность переменных окружения'
    )
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def get_api_answer(current_timestamp: int) -> dict:
    """Делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': current_timestamp}
    }
    if not isinstance(current_timestamp, (float, int)):
        raise EndPointError('Неверный формат даты')
    logger.debug(
        f'Отправляем запрос с параметрами: {request_params}'
    )
    response = requests.get(**request_params)
    if response.status_code == HTTPStatus.OK:
        return response.json()
    if response.status_code == HTTPStatus.NOT_FOUND:
        raise EndPointError(f'Нет ответа API: {response.status_code}')
    else:
        response = response.json()
        answer_code = response.get('code')
        answer_error = response.get('error')
        if not answer_code:
            raise EndPointError(f'Нет ответа API: {answer_error}')
        else:
            raise EndPointError(f'Нет ответа API: {answer_code}')


def check_response(response: Dict[str, List[dict]]) -> list:
    """Проверяет ответ API на корректность.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ (он может быть и пустым),
    доступный в ответе API по ключу 'homeworks'.
    """
    logger.debug(
        'Проверяем ответ API на корректность.'
    )
    if not isinstance(response, dict):
        raise TypeError('Ответ API отличен от словаря')
    if 'homeworks' not in response:
        raise KeyError('Ошибка словаря по ключу homeworks')
    list_homeworks = response['homeworks']
    if not isinstance(list_homeworks, list):
        raise TypeError(
            'Оттвет от API под ключом `homeworks`'
            + ' домашки приходят не в виде списка'
        )
    if not list_homeworks:
        raise ListEmptyError('Список работ пуст')
    return list_homeworks


def parse_status(homework: Dict[str, str]) -> str:
    """Извлекает из информации о конкретной домашней работе статус этой работы.
    В качестве параметра функция получает только один элемент из списка
    домашних работ. В случае успеха, функция возвращает подготовленную
    для отправки в Telegram строку,
    содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """
    logger.debug('Извлекаем статус домашней работы')
    if not homework:
        raise DictEmptyError('Домашние работы отсутствуют')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')
    if homework_status not in HOMEWORK_VERDICTS:
        raise UndocumentedStatusError(
            'Недокументированный статус домашней работы,'
            + f'обнаруженный в ответе API: {homework_status}'
        )
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    logger.info(f'Статус работы: {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат.
    определяемый переменной окружения TELEGRAM_CHAT_ID.
    Принимает на вход два параметра:
    экземпляр класса Bot и строку с текстом сообщения.
    """
    try:
        logger.debug(f'Попытка отправить сообщение [ {message} ]')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        raise SendMessageError(error)
    else:
        logger.info(f'Бот отправил сообщение: [ {message} ]')


def main() -> None:
    """Основная логика работы бота."""
    if not check_tokens:
        logger.critical('Отсутствуют одна или несколько переменных окружения')
        print('Программа принудительно остановлена.')
        os._exit(1)
    bot = Bot(token=str(TELEGRAM_TOKEN))
    error_message: str = ''
    current_report = {}
    prev_report = {}
    logger.info('Бот запущен')
    while True:
        try:
            current_timestamp: int = int(time.time())
            response = get_api_answer(current_timestamp)
            list_homeworks = check_response(response)
            logger.info(f'Найдено {len(list_homeworks)} работ')
            for homework in list_homeworks:
                current_report = {
                    'homework_name': homework.get('homework_name'),
                    'message': parse_status(homework),
                    'homework_status': homework.get('status')
                }
                logger.debug('Работа {0} статус {1}'.format(
                    current_report['homework_name'],
                    current_report['homework_status']
                ))
                if current_report != prev_report:
                    send_message(bot, current_report.get('message'))
                    prev_report = current_report.copy()
                time.sleep(SECONDS_MESSAGE_TIMEOUT)
        except Exception as error:
            message = f'Сбой в работе программы - [{error}]'
            logger.error(message)
            if error_message != message:
                send_message(bot, message)
                error_message = message
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        format='[%(levelname)s] %(funcName)s %(lineno)s %(message)s',
        filename='main.log', filemode='w',
        level=logging.INFO
    )
    try:
        main()
    except KeyboardInterrupt:
        print('Выход из программы')
        os._exit(1)
