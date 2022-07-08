import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    filename='main.log',
    filemode='w',
    level=logging.DEBUG)

RETRY_TIME = 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
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
            logging.critical(
                f'Отсутствует обязательная переменная окружения: {name}')
    return result


def get_api_answer(current_timestamp: int) -> dict:
    """
    Делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
    if response.status_code != HTTPStatus.OK:
        logging.error(f'Ошибка! Код ответа API: {response.status_code}')
        raise Exception(f'Ошибка! Код ответа API: {response.status_code}')
    try:
        return response.json()
    except ValueError:
        logging.error('Ошибка парсинга ответа из формата json')
        raise ValueError('Ошибка парсинга ответа из формата json')


def check_response(response):
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
    try:
        homework = list_homeworks[0]
    except IndexError:
        raise IndexError('Список домашних работ пуст')
    return homework


def parse_status(homework):
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.
    В качестве параметра функция получает только один элемент из списка домашних работ.
    В случае успеха, функция возвращает подготовленную для отправки в Telegram строку,
    содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """

    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(
            f'Недокументированный статус домашней работы, обнаруженный в ответе API: {homework_status}')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    logging.info(f'Статус работы: {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message) -> None:
    """
    Отправляет сообщение в Telegram чат, определяемый переменной окружения TELEGRAM_CHAT_ID.
    Принимает на вход два параметра: экземпляр класса Bot и строку с текстом сообщения.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения: {error}')
    else:
        logging.info(f'Бот отправил сообщение: {message}')


def main():
    """Основная логика работы бота."""

    if not check_tokens:
        print('Программа принудительно остановлена.')
        sys.exit(1)

    bot = Bot(token=TELEGRAM_TOKEN)
    # current_timestamp = int(time.time())
    current_timestamp = 1654065681
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) > 0:
                for homework in homeworks:
                    message = parse_status(homework)
            else:
                logging.info(f'Статус домашки не изменился!')
                current_timestamp = int(time.time())
                time.sleep(RETRY_TIME)
                continue
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            time.sleep(RETRY_TIME)
        else:
            send_message(bot, message)


if __name__ == '__main__':
    main()
