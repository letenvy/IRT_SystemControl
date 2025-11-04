import RPi.GPIO as GPIO
import time

# Номера пинов по BCM
TRIG = 10
ECHO = 9

# Инициализация GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

GPIO.output(TRIG, False)
print("Сонар запущен... Ждите измерений.")

try:
    while True:
        # Отправляем импульс
        GPIO.output(TRIG, True)
        time.sleep(0.00001)  # 10 мкс
        GPIO.output(TRIG, False)

        # Ждём начало эха
        while GPIO.input(ECHO) == 0:
            pulse_start = time.time()

        # Ждём конец эха
        while GPIO.input(ECHO) == 1:
            pulse_end = time.time()

        # Вычисляем расстояние
        pulse_duration = pulse_end - pulse_start
        distance = (pulse_duration * 34300) / 2  # см

        if distance > 400 or distance < 2:
            print("Расстояние за пределами диапазона")
        else:
            print(f"Расстояние: {distance:.1f} см")

        time.sleep(0.5)

except KeyboardInterrupt:
    print("Тест завершён.")
finally:
    GPIO.cleanup()