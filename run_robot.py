'''
Script consists of 4 threads:
1 - HMI: Set target-point (x,y)
2 - Read data from UWB
3 - Read data from MAGNETOMETER
4 - Control algorithm
'''

import threading
import time
import queue
import serial
import re

from UWBparser import read_sensor_data
from Magnit_Class_copy import HMC5883L
from robot import DifferentialDriveRobot
from control_algorithm_thread import control_algorithm_thread

# === Настройки GPIO ===
ROBOT_PINS = {
    'left_enable': 13,
    'left_pin1': 19,
    'left_pin2': 16,
    'right_enable': 20,
    'right_pin1': 21,
    'right_pin2': 26,
}

# === Глобальные объекты ===
data_queue = queue.Queue()
stop_event = threading.Event()
compas = None  # ← объявляем глобально


# === Поток UWB ===
def uwb_thread(port='/dev/ttyACM0', baudrate=115200, max_no_data_time=5):
    ser = None
    try:
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=1)
        print("[UWB] Подключение установлено")
        last_valid_time = time.time()

        while not stop_event.is_set():
            if ser.in_waiting:
                line = ser.readline().decode('ascii', errors='ignore').strip()
                if len(line) > 10:
                    match = re.search(r"\[SOLVE\].*?X:\s*([\d\.\-]+)\s*Y:\s*([\d\.\-]+)", line)
                    if match:
                        x, y = float(match.group(1)), float(match.group(2))
                        data_queue.put({'type': 'position', 'value': (x, y)})
                        last_valid_time = time.time()
            if time.time() - last_valid_time > max_no_data_time:
                print("[UWB] Переподключение...")
                ser.close()
                time.sleep(1)
                ser = serial.Serial(port=port, baudrate=baudrate, timeout=1)
                last_valid_time = time.time()
            time.sleep(0.01)
    except Exception as e:
        print(f"[UWB] Ошибка: {e}")
    finally:
        if ser and ser.is_open:
            ser.close()


# === Поток магнитометра ===
def mag_thread(mag_sensor):
    while not stop_event.is_set():
        try:
            heading = mag_sensor.heading()
            data_queue.put({'type': 'heading', 'value': heading})
            time.sleep(0.1)
        except Exception as e:
            print(f"[MAG] Ошибка: {e}")
            time.sleep(1)


# === Поток HMI ===
def hmi_thread():
    print("\n[HMI] Введите команды:")
    print("  calibrate    — запуск процесса калибровки")
    print("  target x y   — задать цель")
    print("  start        — начать движение")
    print("  stop         — остановить")
    print("  quit         — завершить\n")
    while not stop_event.is_set():
        try:
            cmd = input().strip().split()
            if not cmd:
                continue
            if cmd[0] == 'quit':
                stop_event.set()
                break
            elif cmd[0] == 'stop':
                data_queue.put({'type': 'command', 'value': 'stop'})
            elif cmd[0] == 'start':
                data_queue.put({'type': 'command', 'value': 'start'})
            elif cmd[0] == 'target' and len(cmd) == 3:
                x, y = float(cmd[1]), float(cmd[2])
                data_queue.put({'type': 'target', 'value': (x, y)})
            elif cmd[0] == 'calibrate':
                # Теперь compas доступен глобально
                print("[HMI] Запуск калибровки...")
                compas.calibrate()  # ← должен быть реализован в Magnit_Class_copy.py
            else:
                print("[HMI] Неверная команда. Повторите.")
        except (EOFError, KeyboardInterrupt):
            stop_event.set()
            break


# === MAIN ===
if __name__ == "__main__":
    robot = None

    try:
        print("Инициализация робота...")
        robot = DifferentialDriveRobot(**ROBOT_PINS)

        print("Инициализация магнитометра...")
        compas = HMC5883L(gauss=8.1, declination=(7, 22), controlRobot=robot)

        threads = [
            threading.Thread(target=uwb_thread, daemon=True),
            threading.Thread(target=mag_thread, args=(compas,), daemon=True),
            threading.Thread(target=hmi_thread, daemon=True),
            threading.Thread(
                target=control_algorithm_thread,
                args=(data_queue, robot, stop_event),
                kwargs={
                    'linear_speed': 40,
                    'angular_speed': 80,
                    'stop_radius': 0.1
                },
                daemon=True
            ),
        ]

        for t in threads:
            t.start()

        print("\n✅ Система запущена!\n")

        while not stop_event.is_set():
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[MAIN] Получен сигнал прерывания (Ctrl+C)")
        stop_event.set()
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
    finally:
        stop_event.set()
        time.sleep(1)
        if robot:
            robot.cleanup()
        print("✅ Завершено.")