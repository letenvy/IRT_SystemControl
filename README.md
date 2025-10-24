# cloudbots

## Подключение

### адресс сервера: wss://hackmpei.ru:9001/robot или wss://194.67.86.110:9001/robot(если проблемы с днс)

все сообщения отправляются в формате json

## Аутентификация

После установления WebSocket-соединения робот должен пройти аутентификацию. Без нее робот не будет получать сообщения от пользователя и с координатами других роботов. Для этого используется действие device_login.

* *Формат сообщения*

```json
{
    "action": "device_login",
    "payload": {
        "name": "Имя_робота",
        "password": "Пароль_робота"
    }
}
```

* *Ответ сервера*

```json
{
    "status": "success",
    "action": "device_login",
    "message": "Logged in successfully",
    "data": {
        "api_key": "API_KEY_РОБОТА",
        "car_id": "CAR_ID_РОБОТА"
    }
}
```

Все последующие сообщения от робота должны содержать поле apikey с API-ключом, полученным при аутентификации.

```json
{
    "apikey": "API_KEY_РОБОТА",
    "action": "...",
    "payload": { ... }
}
```

## Действия робота (исходящие сообщения)

### Отправка позиции робота

* *Формат сообщения*

```json
{
    "apikey": "API_KEY_РОБОТА",
    "action": "send_telemetry",
    "payload": {
        "x": 10.5,
        "y": 20.2,
        "w_x": 0.0,
        "w_y": 0.0,
        "w_z": 1.0
    }
}
```

* *Ответ сервера*

```json
{
    "status": "success",
    "action": "send_telemetry",
    "message": "Telemetry data sent",
    "data": null
}
```

### Отправка логов

* *Формат сообщения*

```json
{
    "apikey": "API_KEY_РОБОТА",
    "action": "send_log",
    "payload": {
        "message": "Текст лога"
    }
}
```

* *Ответ сервера*

```json
{
    "status": "success",
    "action": "send_log",
    "message": "Log data sent",
    "data": null
}
```

### WebRTC

* *Формат сообщения*

```json
{
    "apikey": "API_KEY_РОБОТА",
    "action": "offer" | "answer" | "candidate",
    "payload": {
        // Зависит от action.  Обычно содержит sdp или candidate.
        "sdp": { ... }, // Для offer и answer
        "candidate": { ... } // Для candidate
    }
}
```

* *Ответ сервера*

```json
{
    "status": "success",
    "action": "<исходное_действие>",
    "message": "sdp sent to user",
    "data": null
}
```

## Действия, получаемые роботом (входящие сообщения)

Робот получает сообщения от сервера в следующих случаях:

### Уведомление о том, что робот выбран пользователем

* *Ответ сервера*

```json
{
    "action": "car_selected",
    "payload": {
        "user_id": "USER_ID"
    }
}
```

### Уведомление о том, что пользователь освободил робота

* *Ответ сервера*

```json
{
    "action": "car_released",
    "payload": {
        "user_id": "USER_ID"
    }
}
```

### Команда от пользователя

* *Ответ сервера*

```json
{
    "action": "send_command",
    "payload": {
        "command": "..."
    }
}
```

### Отправка файла пользователем

* *Ответ сервера*

```json
{
    "action": "send_file",
    "payload": {
        "body": "Тело файла",
        "extension": "Расширение файла"
    }
}
```

### Отправка прошивки пользователем

* *Ответ сервера*

```json
{
    "action": "send_firmware",
    "payload": {
        "filename": "Имя файла",
        "content": "Содержимое файла"
    }
}
```

### Сообщение о позиции робота

* *Ответ сервера*

```json
{
    "action": "car_position",
    "payload": {
        "car_id": "CAR_ID",
        "role": "car" | "taxi",
        "x": 10.5,
        "y": 20.2,
        "w_x": 0.1,
        "w_y": 0.2,
        "w_z": 0.3
    }
}
```

## Поддержание соединения (ping/pong)

Сервер регулярно отправляет ping сообщения. Робот должен отвечать на них pong сообщениям. Если сервер не получает pong в течение определенного времени (45 секунд), соединение закрывается.
