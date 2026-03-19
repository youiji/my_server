import logging
import socket
from typing import Tuple


# =========================
# НАСТРОЙКИ ПО УМОЛЧАНИЮ
# =========================
# Эти значения будут предложены пользователю,
# если он просто нажмет Enter и ничего не введет.
DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 9090
BUFFER_SIZE = 1024
LOG_FILE = 'server.log'
MAX_PORT = 65535


# =========================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# =========================
# По заданию служебные сообщения сервера должны идти не в консоль,
# а в специальный лог-файл.
# Поэтому используем модуль logging и пишем все рабочие события в файл.
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    encoding='utf-8'
)


def ask_host(default_host: str) -> str:
    """
    Безопасно спрашивает у пользователя IP-адрес / имя хоста,
    на котором сервер будет слушать подключения.

    Для сервера чаще всего используют:
    - 0.0.0.0  -> слушать все сетевые интерфейсы
    - 127.0.0.1 -> слушать только локальный компьютер

    Если пользователь ничего не ввел, возвращаем значение по умолчанию.
    """
    while True:
        user_input = input(
            f'Введите адрес хоста для сервера '
            f'[по умолчанию {default_host}]: '
        ).strip()

        # Если пользователь просто нажал Enter,
        # берем значение по умолчанию.
        if user_input == '':
            return default_host

        # Здесь мы не делаем слишком жесткую проверку имени хоста,
        # потому что ОС сама умеет обрабатывать многие допустимые варианты.
        # Но проверяем хотя бы, что строка не пустая после strip().
        return user_input


def ask_port(default_port: int) -> int:
    """
    Безопасно спрашивает у пользователя номер порта.

    Требования к порту:
    - должен быть целым числом;
    - должен лежать в диапазоне 1..65535.

    Если пользователь ничего не ввел, возвращаем порт по умолчанию.
    """
    while True:
        user_input = input(
            f'Введите начальный порт для сервера '
            f'[по умолчанию {default_port}]: '
        ).strip()

        if user_input == '':
            return default_port

        if not user_input.isdigit():
            print('Ошибка: порт должен быть целым положительным числом.')
            continue

        port = int(user_input)

        if 1 <= port <= MAX_PORT:
            return port

        print(f'Ошибка: порт должен быть в диапазоне 1..{MAX_PORT}.')


def bind_to_free_port(server_socket: socket.socket,
                      host: str,
                      start_port: int) -> int:
    """
    Пытается привязать серверный сокет к порту start_port.

    Если порт занят, автоматически пробует следующий:
    start_port + 1, start_port + 2 и так далее,
    пока не найдет свободный порт.

    Возвращает фактический порт, к которому удалось привязаться.

    Это и есть реализация требования:
    "сервер должен автоматически изменять номер порта,
    если он уже занят".
    """
    current_port = start_port

    while current_port <= MAX_PORT:
        try:
            server_socket.bind((host, current_port))
            return current_port
        except OSError:
            # Чаще всего здесь причина в том, что порт уже занят.
            # Пробуем следующий порт.
            current_port += 1

    raise OSError(
        f'Не удалось найти свободный порт в диапазоне {start_port}..{MAX_PORT}.'
    )


def receive_lines_from_client(conn: socket.socket,
                              client_address: Tuple[str, int]) -> None:
    """
    Обрабатывает одного подключившегося клиента.

    ВАЖНО ДЛЯ НОВИЧКА:
    TCP не сохраняет границы сообщений.
    Это означает, что если клиент отправил две строки,
    сервер при recv() может получить:
    - одну строку целиком,
    - половину строки,
    - две строки сразу,
    - кусок строки + кусок следующей строки.

    Поэтому для "строкового" протокола мы вводим простое правило:
    каждая строка заканчивается символом '\n'.

    Сервер накапливает данные в буфере и извлекает из него
    готовые строки по символу новой строки.
    """
    # Буфер, куда складываем куски TCP-потока,
    # пока из них не получится хотя бы одна полная строка.
    text_buffer = ''

    # Используем with, чтобы клиентский сокет корректно закрылся
    # автоматически после выхода из блока.
    with conn:
        logging.info(
            'Подключен клиент: IP=%s, PORT=%s',
            client_address[0],
            client_address[1]
        )

        while True:
            data = conn.recv(BUFFER_SIZE)

            # Если recv() вернул пустые байты b'',
            # значит клиент закрыл соединение.
            if not data:
                logging.info(
                    'Клиент %s:%s разорвал соединение.',
                    client_address[0],
                    client_address[1]
                )
                break

            # Декодируем принятый кусок в строку.
            # errors='replace' нужен, чтобы сервер не падал,
            # если внезапно придут некорректные байты.
            chunk_text = data.decode('utf-8', errors='replace')
            logging.info(
                'Получено %s байт от клиента %s:%s: %r',
                len(data),
                client_address[0],
                client_address[1],
                chunk_text
            )

            # Добавляем новый текст к накопленному буферу.
            text_buffer += chunk_text

            # Пока в буфере есть символ перевода строки,
            # значит в буфере есть как минимум одна полностью полученная строка.
            while '\n' in text_buffer:
                # Делим буфер на первую готовую строку и оставшийся "хвост".
                line, text_buffer = text_buffer.split('\n', 1)

                # Удаляем возможный символ '\r',
                # если клиент отправил строку в стиле Windows: \r\n
                line = line.rstrip('\r')

                logging.info(
                    'Полностью получена строка от %s:%s: %r',
                    client_address[0],
                    client_address[1],
                    line
                )

                # По условию задания строка "exit"
                # считается командой разрыва соединения со стороны клиента.
                if line == 'exit':
                    logging.info(
                        'От клиента %s:%s получена команда завершения "exit".',
                        client_address[0],
                        client_address[1]
                    )

                    # При желании можно отправить клиенту подтверждение,
                    # чтобы он понял, что команда обработана сервером.
                    goodbye_message = 'Соединение будет закрыто по команде exit.\n'
                    conn.sendall(goodbye_message.encode('utf-8'))
                    logging.info(
                        'Клиенту %s:%s отправлено сообщение о закрытии соединения.',
                        client_address[0],
                        client_address[1]
                    )
                    return

                # Если это не exit, сервер работает как эхо-сервер:
                # возвращает клиенту ту же строку обратно.
                response = line + '\n'
                response_bytes = response.encode('utf-8')
                conn.sendall(response_bytes)

                logging.info(
                    'Клиенту %s:%s отправлено %s байт: %r',
                    client_address[0],
                    client_address[1],
                    len(response_bytes),
                    response
                )


def main() -> None:
    """
    Основная функция сервера.

    Здесь мы:
    1. спрашиваем у пользователя host и начальный port;
    2. создаем TCP-сокет;
    3. автоматически ищем свободный порт, если выбранный занят;
    4. начинаем слушать этот порт;
    5. в бесконечном цикле принимаем клиентов;
    6. после отключения одного клиента НЕ завершаем сервер,
       а продолжаем ждать следующих подключений.
    """
    host = ask_host(DEFAULT_HOST)
    start_port = ask_port(DEFAULT_PORT)

    # Создаем TCP-сокет IPv4.
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # SO_REUSEADDR помогает быстрее перезапускать сервер во время отладки.
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        logging.info('Запуск сервера.')
        logging.info('Пользователь выбрал host=%s, start_port=%s.', host, start_port)

        # Пытаемся привязаться к свободному порту.
        actual_port = bind_to_free_port(server_socket, host, start_port)

        logging.info(
            'Сервер успешно привязан к адресу %s и порту %s.',
            host,
            actual_port
        )

        # По заданию номер порта, который реально слушает сервер,
        # должен выводиться в консоль.
        print(f'Сервер слушает порт: {actual_port}')
        print(f'Служебные сообщения записываются в файл: {LOG_FILE}')

        # Переводим сокет в режим ожидания подключений.
        # backlog=5 означает очередь из нескольких ожидающих клиентов.
        server_socket.listen(5)
        logging.info('Начато прослушивание порта %s.', actual_port)

        # Бесконечный цикл сервера.
        # ВАЖНО: после отключения одного клиента сервер не завершается,
        # а снова вызывает accept() и ждет нового клиента.
        while True:
            logging.info('Ожидание нового подключения клиента...')
            conn, addr = server_socket.accept()
            receive_lines_from_client(conn, addr)

    except KeyboardInterrupt:
        # Сервер можно остановить Ctrl+C.
        logging.info('Сервер остановлен пользователем через Ctrl+C.')
        print('\nСервер остановлен.')

    except Exception as error:
        logging.exception('Ошибка в работе сервера: %s', error)
        print(f'Ошибка сервера: {error}')

    finally:
        server_socket.close()
        logging.info('Серверный сокет закрыт.')


if __name__ == '__main__':
    main()
