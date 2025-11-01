import RPi.GPIO as GPIO
import time
import math

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

    def __set_motor_direction(self, side, direction):
        """
        Устанавливает направление вращения для указанной стороны.
        
        side: 'left' или 'right'
        direction: 'forward', 'backward', 'stop'
        """
        #print(f"[Debug] Установка направления: {side} -> {direction}")
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
        #print(f"[Robot] Установка скорости: левый={left_speed}, правый={right_speed}")

        # Левый мотор
        if left_speed >= 0:
            self.__set_motor_direction('left', 'forward')
            duty = min(100, left_speed)
        else:
            self.__set_motor_direction('left', 'backward')
            duty = min(100, -left_speed)
        self.pwm_left.ChangeDutyCycle(duty)
        #print(f"[Debug] Левый мотор: скважность = {duty}%")

        # Правый мотор
        if right_speed >= 0:
            self.__set_motor_direction('right', 'forward')
            duty = min(100, right_speed)
        else:
            self.__set_motor_direction('right', 'backward')
            duty = min(100, -right_speed)
        self.pwm_right.ChangeDutyCycle(duty)
        #print(f"[Debug] Правый мотор: скважность = {duty}%")

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

    def go_to_point(self, current_x, current_y, target_x, target_y,
                    current_heading_deg, linear_speed=60, Kp=1.0,
                    stop_radius=0.1, max_angular_speed=70):
        """
        Движение к точке с поддержкой танкового разворота при больших углах ошибки.
        Все позиции — в метрах. Углы — в градусах (азимут: 0° = север, + по часовой).
        """
        dx = target_x - current_x
        dy = target_y - current_y
        distance = math.hypot(dx, dy)

        if distance <= stop_radius:
            self.stop()
            return True

        # === Перевод цели в азимут от севера (как у магнитометра) ===
        # atan2(dy, dx) → угол от востока против ЧС
        # Нам нужно: 0° = север, + по ЧС → формула:
        target_angle_deg = (90.0 - math.degrees(math.atan2(dy, dx))) % 360.0

        # === Нормализация разницы углов к [-180, +180] ===
        angle_diff = target_angle_deg - (current_heading_deg % 360.0)
        while angle_diff > 180:
            angle_diff -= 360
        while angle_diff < -180:
            angle_diff += 360
        print(f"[DEBUG] tgt=({target_x:.2f},{target_y:.2f}) pos=({current_x:.2f},{current_y:.2f}) "f"hdg={current_heading_deg:6.1f}° tgt_ang={target_angle_deg:6.1f}° diff={angle_diff:6.1f}°")
        # === Порог для танкового разворота (градусы) ===
        TURN_THRESHOLD =30.0  # можно настроить
        DEADBAND = 3.0  # ±3° — не корректируем

        if abs(angle_diff) < DEADBAND:
            # Угол выровнен — можно ехать прямо
            self.set_speed(linear_speed, linear_speed)
            return False

        if abs(angle_diff) > TURN_THRESHOLD:
            # ТАНКОВЫЙ РАЗВОРОТ
            direction = 1 if angle_diff > 0 else -1
            left_speed = -max_angular_speed * direction
            right_speed = max_angular_speed * direction
            self.set_speed(left_speed, right_speed)
        else:
            # МЯГКАЯ КОРРЕКЦИЯ (с уменьшенным Kp)
            correction = Kp * angle_diff
            left_speed = linear_speed - correction
            right_speed = linear_speed + correction
            left_speed = max(-100, min(100, left_speed))
            right_speed = max(-100, min(100, right_speed))
            self.set_speed(left_speed, right_speed)

        return False


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
        try:
            # Проверяем, существует ли атрибут pwm_left (не был ли уже удалён)
            if hasattr(self, 'pwm_left'):
                self.cleanup()
        except Exception as e:
            # Подавляем ошибки, если GPIO уже сброшен
            pass