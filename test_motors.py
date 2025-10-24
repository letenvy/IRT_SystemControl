# test_motors.py
import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Настройка пинов (должны совпадать с вашим подключением)
LEFT_ENABLE = 13
LEFT_PIN1 = 19
LEFT_PIN2 = 16

RIGHT_ENABLE = 20
RIGHT_PIN1 = 21
RIGHT_PIN2 = 26

# Инициализация
GPIO.setup(LEFT_ENABLE, GPIO.OUT)
GPIO.setup(LEFT_PIN1, GPIO.OUT)
GPIO.setup(LEFT_PIN2, GPIO.OUT)
GPIO.setup(RIGHT_ENABLE, GPIO.OUT)
GPIO.setup(RIGHT_PIN1, GPIO.OUT)
GPIO.setup(RIGHT_PIN2, GPIO.OUT)

pwm_left = GPIO.PWM(LEFT_ENABLE, 100)
pwm_right = GPIO.PWM(RIGHT_ENABLE, 100)
pwm_left.start(0)
pwm_right.start(0)

def motor_test():
    try:
        print("Тест моторов запущен!")
        
        # Вперед 2 секунды
        print("Движение вперед")
        GPIO.output(LEFT_PIN1, GPIO.HIGH)
        GPIO.output(LEFT_PIN2, GPIO.LOW)
        GPIO.output(RIGHT_PIN1, GPIO.HIGH)
        GPIO.output(RIGHT_PIN2, GPIO.LOW)
        pwm_left.ChangeDutyCycle(50)
        pwm_right.ChangeDutyCycle(50)
        time.sleep(2)
        
        # Поворот направо 1 секунда
        print("Поворот направо")
        GPIO.output(RIGHT_PIN1, GPIO.LOW)
        GPIO.output(RIGHT_PIN2, GPIO.HIGH)
        time.sleep(1)
        
        # Поворот налево 1 секунда
        print("Поворот налево")
        GPIO.output(LEFT_PIN1, GPIO.LOW)
        GPIO.output(LEFT_PIN2, GPIO.HIGH)
        time.sleep(1)
        
        # Назад 2 секунды
        print("Движение назад")
        GPIO.output(LEFT_PIN1, GPIO.LOW)
        GPIO.output(LEFT_PIN2, GPIO.HIGH)
        GPIO.output(RIGHT_PIN1, GPIO.LOW)
        GPIO.output(RIGHT_PIN2, GPIO.HIGH)
        time.sleep(2)
        
    finally:
        print("Остановка")
        pwm_left.stop()
        pwm_right.stop()
        GPIO.cleanup()

if __name__ == "__main__":
    motor_test()