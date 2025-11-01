'''
Script consists of 3 threads:
1 - HMI: Set target-point (x,y)
2 - Read data from UWB
3 - Read data from MAGNITOMETER
4 - Control algorithm

Queue of string:
Input: 1, 2, 3 threads
Output: 4 thread

'''

import threading
import time
import queue
import serial
import re

from UWBparser import read_sensor_data  # если вы его не меняли — лучше не использовать напрямую
from Magnit_Class_copy import HMC5883L
from robot import DifferentialDriveRobot
#from ControlAlgorithmRobot import control_algorithm_thread  # ← импорт нового модуля
from CalibControlAlg import control_algorithm_thread  # ← импорт нового модуля

# === Настройки GPIO (замените на ваши!) ===
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

# === Поток UWB (встроенный, без внешней зависимости) ===
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
                        # print(f'X:{x} Y:{y}')
                        data_queue.put({'type': 'position', 'value': (x, y)})
                        last_valid_time = time.time()
                        
            if time.time() - last_valid_time > max_no_data_time:
                print("[UWB] Переподключение...")
                ser.close()
                time.sleep(1)
                ser = serial.Serial(port=port, baudrate=baudrate, timeout=1)
                last_valid_time = time.time()
            #time.sleep(0.05)
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
            #print("heading = ", heading)
            data_queue.put({'type': 'heading', 'value': heading})
            time.sleep(0.1) #было 0.1!!!!!!!!!
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
                compas.calibrate()
                # data_queue.put({'type': 'command', 'value': 'calibrate'})
            elif cmd[0] == 'calibrate1':
                 data_queue.put({'type': 'command', 'value': 'calibrate1'})
            else:
                print("[HMI] Неверная команда")
        except (EOFError, KeyboardInterrupt):
            stop_event.set()
            break

# === MAIN ===
if __name__ == "__main__":
    robot = None
    try:
        # Инициализация
        print(" Инициализация робота...")
        robot = DifferentialDriveRobot(**ROBOT_PINS)



        print(" Инициализация магнитометра...")
        compas = HMC5883L(gauss=8.1, declination=(7, 22), controlRobot = robot)

        # Создание потоков
        threads = [
            threading.Thread(target=uwb_thread, daemon=True),
            threading.Thread(target=mag_thread, args=(compas,), daemon=True),
            threading.Thread(target=hmi_thread, daemon=True),
            threading.Thread(
                target=control_algorithm_thread,
                args=(data_queue, robot, stop_event),
                kwargs={'linear_speed': 60, 'angular_speed': 30, 'stop_radius': 0.5},
                daemon=True
            ),
        ]

        # Запуск
        for t in threads:
            t.start()

        print("\n Система запущена!\n")

        # Ожидание завершения
        while not stop_event.is_set():
            time.sleep(0.5)

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        stop_event.set()
        time.sleep(1)
        if robot:
            robot.cleanup()
        print("✅ Завершено.")

''' OLD CODE
import asyncio
import serial
import time
import re
import queue

from UWBparser import read_sensor_data
from Magnit_Class import HMC5883L
from robot import DifferentialDriveRobot

msg_queue = queue.Queue()

async def ControlAlgorithm():
	pass


if __name__ == "__main__":
	magnitometer = HMC5883L(gauss=4.7, declination=(7, 22))
	threads = [ threading.Thread(target = read_sensor_data, args = ('/dev/ttyACM0', 115200, reconnect_interval=5, max_no_data_time=5), daemon = true), threading.Thread(target = HMC5883L, args = (4.7, (7, 22)), daemon = true) ]
	#	threads = [ threading.Thread(target = read_sensor_data(port='/dev/ttyACM0', baudrate=115200, reconnect_interval=5, max_no_data_time=5)), threading.Thread(target = magnitometer.heading) ]
	for t in threads:
		t.start()
		
	time.sleep(20)
	
	for t in threads:
		t.join()
'''
