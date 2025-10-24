#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
import threading
from cloud_bots.i2c.i2c_itg3205 import *

# -------------------- ИНИЦИАЛИЗАЦИЯ GPIO --------------------
# Сбрасываем предыдущие настройки (если есть)
GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Пины сервопривода (рулевое управление)
SERVO_PIN = 12

# Пины управления двигателем через драйвер L293D
ENA_PIN = 13    # PWM для мотора
IN1_PIN = 19    # Направление 1
IN2_PIN = 16    # Направление 2

# Пины энкодера (датчики Холла)
ENCODER_PIN_A = 17
ENCODER_PIN_B = 27

TRIG = 23
ECHO = 18

# Настройка пинов
GPIO.setup(SERVO_PIN, GPIO.OUT)
GPIO.setup(ENA_PIN, GPIO.OUT)
GPIO.setup(IN1_PIN, GPIO.OUT)
GPIO.setup(IN2_PIN, GPIO.OUT)
GPIO.setup(ENCODER_PIN_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(ENCODER_PIN_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# -------------------- ИНИЦИАЛИЗАЦИЯ PWM --------------------
# PWM для сервопривода – 50 Гц (стандартно)
servo_pwm = GPIO.PWM(SERVO_PIN, 50)
servo_pwm.start(0)

# PWM для мотора – 100 Гц (как требуется)
motor_pwm = GPIO.PWM(ENA_PIN, 100)
motor_pwm.start(0)

# -------------------- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ЭНКОДЕРА --------------------
encoder_count = 0
# Инициализируем предыдущее состояние энкодера (считываем значения обоих пинов)
prev_state = (GPIO.input(ENCODER_PIN_A), GPIO.input(ENCODER_PIN_B))

# -------------------- ФУНКЦИЯ ОПРОСА ЭНКОДЕРА (без колбэков) --------------------
def poll_encoder():
    """
    Постоянно опрашивает пины энкодера и обновляет счётчик импульсов.
    Преобразование состояний (00, 01, 10, 11) в число от 0 до 3,
    затем вычисляется разница между предыдущим и текущим состоянием.
    """
    global encoder_count, prev_state
    while True:
        current_state = (GPIO.input(ENCODER_PIN_A), GPIO.input(ENCODER_PIN_B))
        if current_state != prev_state:
            # Преобразуем состояния в число: (MSB << 1) | LSB
            prev_val = (prev_state[0] << 1) | prev_state[1]
            curr_val = (current_state[0] << 1) | current_state[1]
            delta = (curr_val - prev_val) % 4
            if delta == 1:
                encoder_count += 1
            elif delta == 3:
                encoder_count -= 1
            prev_state = current_state
        sleep(0.001)  # задержка 1 мс для снижения нагрузки на процессор

# Запускаем опрос энкодера в отдельном потоке (daemon-поток завершится при выходе из программы)
encoder_thread = threading.Thread(target=poll_encoder, daemon=True)
encoder_thread.start()
itg3205 = i2c_itg3205(1)
# -------------------- ИНИЦИАЛИЗАЦИЯ ГИРОСКОПА --------------------

# -------------------- ФУНКЦИЯ ДЛЯ СЕРВОПРИВОДА --------------------
def set_servo_angle(angle):
    """
    Устанавливает угол сервопривода (0°...180°).
    Для MG996R часто: 0° соответствует ~2.5% duty cycle, 180° — ~12.5%.
    Задержка уменьшена до 0.1 с для быстрой реакции.
    """
    duty = (angle / 18.0) + 2.5
    servo_pwm.ChangeDutyCycle(duty)
    sleep(0.1)
    servo_pwm.ChangeDutyCycle(0)

# -------------------- ФУНКЦИИ ДЛЯ ДВИГАТЕЛЯ --------------------
def MotorForward(speed):
    """
    Движение вперёд. Параметр speed задаёт скорость (0-100% PWM).
    """
    GPIO.output(IN1_PIN, GPIO.HIGH)
    GPIO.output(IN2_PIN, GPIO.LOW)
    motor_pwm.ChangeDutyCycle(speed)

def MotorBackward(speed):
    """
    Движение назад.
    """
    GPIO.output(IN1_PIN, GPIO.LOW)
    GPIO.output(IN2_PIN, GPIO.HIGH)
    motor_pwm.ChangeDutyCycle(speed)

def MotorStop():
    """
    Останавливает мотор.
    """
    GPIO.output(IN1_PIN, GPIO.LOW)
    GPIO.output(IN2_PIN, GPIO.LOW)
    motor_pwm.ChangeDutyCycle(0)

# -------------------- ФУНКЦИЯ ПОВОРОТА РОБОТА --------------------
def turn_robot(target_angle_deg, base_speed=80):
    """
    Поворачивает робота на заданный угол (в градусах) с использованием гироскопа.
    
    Положительный угол (например, 90°) – поворот влево, отрицательный – вправо.
    
    Во время поворота:
      - Сервопривод устанавливается в соответствующее положение:
          • 0° для поворота влево,
          • 72° для поворота вправо.
      - Интегрируются показания угловой скорости гироскопа.
      - Скорость мотора корректируется пропорционально оставшейся ошибке.
      - Счётчик энкодера используется для контроля переезда (защита от избыточного поворота).
    """
    # Переводим целевой угол в радианы
    target_angle = math.radians(target_angle_deg)
    dt = 0.02  # интервал цикла 20 мс
    tolerance = math.radians(1)  # допускаемая погрешность 1°
    
    # Пропорциональный коэффициент для регуляции скорости
    proportional_gain = base_speed / abs(target_angle) if target_angle != 0 else 0
    min_speed = 40   # минимальная скорость для преодоления инерции
    max_speed = base_speed
    
    global encoder_count
    encoder_count = 0  # сброс счетчика энкодера
    
    # Установка угла сервопривода: для поворота вправо (отрицательный угол) – 72°, для поворота влево – 0°
    if target_angle_deg < 0:
        set_servo_angle(65)
    else:
        set_servo_angle(5)
    
    # Получаем начальное значение угловой скорости по оси Z
    try:
        _, _, start_z = itg3205.getDegPerSecAxes()
    except OSError:
        print("Ошибка чтения гироскопа при инициализации.")
        start_z = 0
    
    current_angle = 0.0  # интегрированный угол поворота (в радианах)
    print(f"Начало поворота на {target_angle_deg}°")
    MotorForward(base_speed)
    start_time = time()
    
    # Порог по количеству импульсов энкодера (экспериментально подбирается)
    MAX_ENCODER_COUNT = 50
    
    while abs(target_angle - current_angle) > tolerance:
        loop_start = time()
        try:
            # Считываем текущую угловую скорость по оси Z (в градусах/сек)
            _, _, z = itg3205.getDegPerSecAxes()
        except OSError:
            print("Ошибка чтения гироскопа, пропуск итерации.")
            continue
        
        # Интегрируем угловую скорость: преобразуем (z - start_z) из град/сек в радианы
        current_angle += -math.radians(z - start_z) * dt
        error = target_angle - current_angle
        computed_speed = proportional_gain * abs(error)
        speed = max(min_speed, min(max_speed, computed_speed))
        
        # Если счётчик энкодера превышает порог, ограничиваем скорость для избежания переезда
        if abs(encoder_count) > MAX_ENCODER_COUNT:
            speed = min(speed, 30)
            print(f"Превышен порог энкодера: {encoder_count} импульсов")
        
        MotorForward(speed)
        
        # Отладочный вывод
        print(f"Цель: {math.degrees(target_angle):.2f}°, Текущий: {math.degrees(current_angle):.2f}°, "
              f"Ошибка: {math.degrees(error):.2f}°, Скорость: {speed:.1f}%, Энкодер: {encoder_count}")
        
        elapsed = time() - loop_start
        if dt - elapsed > 0:
            sleep(dt - elapsed)
    
    MotorStop()
    # Возвращаем сервопривод в нейтральное положение (36°)
    set_servo_angle(36)
    total_time = time() - start_time
    print(f"Поворот завершён. Итоговый угол: {math.degrees(current_angle):.2f}°, "
          f"Время: {total_time:.2f} сек, Импульсов энкодера: {encoder_count}")

# -------------------- ОСНОВНАЯ ПРОГРАММА --------------------
if __name__ == '__main__':
    try:
        # Пример: поворот налево на 90° (для поворота вправо используйте отрицательное значение, например, -90)
        turn_robot(-85, base_speed=90)
        # Здесь можно добавить дополнительные команды для движения или последовательности поворотов.
        
    except KeyboardInterrupt:
        print("Прервано пользователем.")
    finally:
        MotorStop()
