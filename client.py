import socket


# =========================
# НАСТРОЙКИ ПО УМОЛЧАНИЮ
# =========================
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 9090
BUFFER_SIZE = 1024
MAX_PORT = 65535


def ask_host(default_host: str) -> str:
    """
    Безопасно запрашивает у пользователя имя хоста или IP-адрес сервера.

    Если пользователь ничего не ввел, берется значение по умолчанию.
    """
    while True:
        user_input = input(
            f'Введите адрес сервера [по умолчанию {default_host}]: '
        ).strip()

        if user_input == '':
            return default_host

        return user_input


def ask_port(default_port: int) -> int:
    """
    Безопасно запрашивает номер порта.

    Проверяем, что:
    - пользователь ввел число;
    - число в диапазоне 1..65535.
    """
    while True:
        user_input = input(
            f'Введите порт сервера [по умолчанию {default_port}]: '
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


def receive_line_from_server(client_socket: socket.socket) -> str:
    """
    Принимает от сервера ровно одну строку, заканчивающуюся символом '\n'.

    Почему это нужно?
    Потому что TCP - потоковый протокол.
    У него нет понятия "одно сообщение = один recv()".
    Поэтому клиент должен сам собирать строку из кусочков,
    пока не встретит символ конца строки.
    """
    text_buffer = ''

    while True:
        data = client_socket.recv(BUFFER_SIZE)

        if not data:
            # Если сервер неожиданно закрыл соединение,
            # возвращаем то, что успели собрать.
            return text_buffer

        text_buffer += data.decode('utf-8', errors='replace')

        if '\n' in text_buffer:
            line, _rest = text_buffer.split('\n', 1)
            return line.rstrip('\r')


def main() -> None:
    """
    Основная функция клиента.

    Новый вариант клиента работает в цикле:
    1. подключается к серверу;
    2. спрашивает у пользователя строки;
    3. отправляет их серверу;
    4. получает эхо-ответ;
    5. завершает работу, когда пользователь вводит "exit".

    ВАЖНО:
    Мы НЕ закрываем соединение после каждой строки.
    Соединение живет до тех пор, пока пользователь не введет "exit"
    или пока сервер не оборвет соединение.
    """
    host = ask_host(DEFAULT_HOST)
    port = ask_port(DEFAULT_PORT)

    print('[КЛИЕНТ] Запуск клиента...')

    # Создаем TCP-сокет клиента.
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Устанавливаем соединение с сервером.
        client_socket.connect((host, port))
        print(f'[КЛИЕНТ] Соединение с сервером установлено: {host}:{port}')

        # Бесконечный цикл общения с сервером.
        while True:
            message = input('Введите строку (для выхода введите exit): ')

            # Добавляем символ новой строки.
            # Это наш простой "протокол": одна логическая строка = один текст + '\n'.
            message_to_send = message + '\n'
            message_bytes = message_to_send.encode('utf-8')

            sent_bytes = 0
            while sent_bytes < len(message_bytes):
                chunk = message_bytes[sent_bytes:sent_bytes + BUFFER_SIZE]
                client_socket.sendall(chunk)
                print(
                    f'[КЛИЕНТ] Отправлено серверу {len(chunk)} байт: '
                    f'{chunk.decode("utf-8", errors="replace")!r}'
                )
                sent_bytes += len(chunk)

            # Если пользователь ввел exit,
            # ждем последнее служебное сообщение от сервера и завершаемся.
            if message == 'exit':
                final_response = receive_line_from_server(client_socket)
                if final_response:
                    print(f'[КЛИЕНТ] Ответ сервера: {final_response!r}')
                print('[КЛИЕНТ] Получена команда завершения. Закрываем клиент.')
                break

            # Для обычной строки ждем эхо-ответ сервера.
            response = receive_line_from_server(client_socket)

            if response == '':
                print('[КЛИЕНТ] Сервер закрыл соединение.')
                break

            print(f'[КЛИЕНТ] Получен ответ от сервера: {response!r}')

    except ConnectionRefusedError:
        print(
            '[КЛИЕНТ] Ошибка: сервер недоступен. '
            'Проверьте, запущен ли server.py и верны ли адрес/порт.'
        )

    except socket.gaierror:
        print(
            '[КЛИЕНТ] Ошибка: не удалось распознать имя хоста. '
            'Проверьте введенный адрес сервера.'
        )

    except Exception as error:
        print(f'[КЛИЕНТ] Ошибка: {error}')

    finally:
        client_socket.close()
        print('[КЛИЕНТ] Разрыв соединения с сервером.')


if __name__ == '__main__':
    main()
