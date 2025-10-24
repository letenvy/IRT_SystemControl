import RPi.GPIO as GPIO
import time

class DifferentialDriveRobot:
    """
    Класс для управления 4-х колёсным роботом с дифференциальным приводом.
    Поддерживает движение вперёд/назад, повороты и тонкое управление скоростью.
    """

    def __init__(self, left_enable, left_pin1, left_pin2,
                 right_enable, right_pin1, right_pin2,
                 pwm_freq=100):
        """
        Инициализация GPIO и ШИМ для управления моторами.
        
        Параметры:
            left_enable, right_enable — пины ШИМ (ENA/ENB)
            left_pin1/2, right_pin1/2 — управляющие пины направления (IN1–IN4)
            pwm_freq — частота ШИМ (Гц)
        """
        print("[Robot] Инициализация робота...")
        self.left_enable = left_enable
        self.left_pin1 = left_pin1
        self.left_pin2 = left_pin2
        self.right_enable = right_enable
        self.right_pin1 = right_pin1
        self.right_pin2 = right_pin2

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Настройка пинов как выходов
        GPIO.setup(self.left_enable, GPIO.OUT)
        GPIO.setup(self.left_pin1, GPIO.OUT)
        GPIO.setup(self.left_pin2, GPIO.OUT)
        GPIO.setup(self.right_enable, GPIO.OUT)
        GPIO.setup(self.right_pin1, GPIO.OUT)
        GPIO.setup(self.right_pin2, GPIO.OUT)

        # Инициализация ШИМ
        self.pwm_left = GPIO.PWM(self.left_enable, pwm_freq)
        self.pwm_right = GPIO.PWM(self.right_enable, pwm_freq)
        self.pwm_left.start(0)
        self.pwm_right.start(0)
        print(f"[Robot] ШИМ запущен: частота {pwm_freq} Гц")

        # Останавливаем моторы при старте
        self.stop()
        print("[Robot] Инициализация завершена.")

    def _set_motor_direction(self, side, direction):
        """
        Устанавливает направление вращения для указанной стороны.
        
        side: 'left' или 'right'
        direction: 'forward', 'backward', 'stop'
        """
        print(f"[Debug] Установка направления: {side} -> {direction}")
        if side == 'left':
            pin1, pin2 = self.left_pin1, self.left_pin2
        elif side == 'right':
            pin1, pin2 = self.right_pin1, self.right_pin2
        else:
            raise ValueError("Side must be 'left' or 'right'")

        if direction == 'forward':
            GPIO.output(pin1, GPIO.HIGH)
            GPIO.output(pin2, GPIO.LOW)
        elif direction == 'backward':
            GPIO.output(pin1, GPIO.LOW)
            GPIO.output(pin2, GPIO.HIGH)
        elif direction == 'stop':
            GPIO.output(pin1, GPIO.LOW)
            GPIO.output(pin2, GPIO.LOW)
        else:
            raise ValueError("Direction must be 'forward', 'backward' or 'stop'")

    def set_speed(self, left_speed, right_speed):
        """
        Устанавливает скорость левого и правого моторов.
        Диапазон: -100 (макс. назад) до +100 (макс. вперёд).
        """
        print(f"[Robot] Установка скорости: левый={left_speed}, правый={right_speed}")

        # Левый мотор
        if left_speed >= 0:
            self._set_motor_direction('left', 'forward')
            duty = min(100, left_speed)
        else:
            self._set_motor_direction('left', 'backward')
            duty = min(100, -left_speed)
        self.pwm_left.ChangeDutyCycle(duty)
        print(f"[Debug] Левый мотор: скважность = {duty}%")

        # Правый мотор
        if right_speed >= 0:
            self._set_motor_direction('right', 'forward')
            duty = min(100, right_speed)
        else:
            self._set_motor_direction('right', 'backward')
            duty = min(100, -right_speed)
        self.pwm_right.ChangeDutyCycle(duty)
        print(f"[Debug] Правый мотор: скважность = {duty}%")

    def stop(self):
        """Полная остановка всех моторов."""
        print("[Robot] Остановка всех моторов.")
        self.set_speed(0, 0)


    def forward(self, speed=50, duration=None):
        """Движение вперёд с заданной скоростью."""
        print(f"[Robot] Движение ВПЕРЁД, скорость={speed}")
        self.set_speed(speed, speed)
        if duration is not None:
            print(f"[Robot] Движение вперёд в течение {duration} сек...")
            time.sleep(duration)
            self.stop()

    def backward(self, speed=50, duration=None):
        """Движение назад с заданной скоростью."""
        print(f"[Robot] Движение НАЗАД, скорость={speed}")
        self.set_speed(-speed, -speed)
        if duration is not None:
            print(f"[Robot] Движение назад в течение {duration} сек...")
            time.sleep(duration)
            self.stop()

    def turn_left(self, speed_left=50,speed_right=100,duration=None):
        print(f"[Robot] Поворот по дуге НАЛЕВО, скорости=(l:{speed_left}, r:{speed_right})")
        self.set_speed(speed_left,speed_right)
        if duration is not None:
            print(f"[Robot] Поворот по дуге налево в течение {duration} сек...")
            time.sleep(duration)
            self.stop()

    def turn_left_tank(self, speed=50, duration=None):
        """Поворот на месте влево (левые колёса назад, правые — вперёд)."""
        print(f"[Robot] Поворот на месте НАЛЕВО, скорость={speed}")
        self.set_speed(-speed, speed)
        if duration is not None:
            print(f"[Robot] Поворот на месте налево в течение {duration} сек...")
            time.sleep(duration)
            self.stop()

    def turn_right(self, speed_left=100,speed_right=50,duration=None):
        print(f"[Robot] Поворот по дуге НАПРАВО, скорости=(l:{speed_left}, r:{speed_right})")
        self.set_speed(speed_left,speed_right)
        if duration is not None:
            print(f"[Robot] Поворот по дуге направо в течение {duration} сек...")
            time.sleep(duration)
            self.stop()

    def turn_right_tank(self, speed=50, duration=None):
        """Поворот на месте вправо (левые колёса вперёд, правые — назад)."""
        print(f"[Robot] Поворот НАПРАВО, скорость={speed}")
        self.set_speed(speed, -speed)
        if duration is not None:
            print(f"[Robot] Поворот направо в течение {duration} сек...")
            time.sleep(duration)
            self.stop()

    def cleanup(self):
        """Очистка ресурсов: остановка ШИМ и сброс GPIO."""
        print("[Robot] Очистка GPIO и остановка ШИМ...")
        self.stop()
        self.pwm_left.stop()
        self.pwm_right.stop()
        GPIO.cleanup()
        print("[Robot] Очистка завершена.")

    def __del__(self):
        """Автоматическая очистка при удалении объекта."""
        print("[Robot] Деструктор вызван. Выполняется cleanup...")
        try:
            self.cleanup()
        except Exception as e:
            print(f"[Warning] Ошибка при автоматической очистке: {e}")
