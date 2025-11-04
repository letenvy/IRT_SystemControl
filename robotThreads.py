# robotThreads.py

import threading
import time
import queue
import serial
import re

from UWBparser import read_sensor_data
from GyroscopeClass import GyroscopeClass  # ← ваш класс
from robot import DifferentialDriveRobot
from ControlAlgorithmRobot import control_algorithm_thread

# === GPIO ===
ROBOT_PINS = {
    'left_enable': 13,
    'left_pin1': 19,
    'left_pin2': 16,
    'right_enable': 20,
    'right_pin1': 21,
    'right_pin2': 26,
}

data_queue = queue.Queue()
stop_event = threading.Event()

# === UWB поток ===
def uwb_thread(port='/dev/ttyACM0', baudrate=115200, max_no_data_time=5):
    ser = None
    try:
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=1)
        print("[UWB] Подключено")
        last_valid_time = time.time()

        while not stop_event.is_set():
            if ser.in_waiting:
                line = ser.readline().decode('ascii', errors='ignore').strip()
                if len(line) > 10:
                    match = re.search(r"\[SOLVE\].*?X:\s*([\d\.\-]+)\s*Y:\s*([\d\.\-]+)", line)
                    if match:
                        x, y = float(match.group(1)), float(match.group(2))
                        # with open("log_coords_and_heading.txt", "a") as file:
                        #     file.write(f"X:{x}\t Y:{y}\n")
                        # print(f"X:{x}\t Y:{y}")
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

# === Гироскоп поток ===
def gyro_thread(gyro_sensor):
    print("[GYRO] Инициализация гироскопа...")
    # Калибровка (опционально — можно загрузить из файла)
    try:
        gyro_sensor.calibrate_and_save("gyro_bias.json", samples=200)
    except Exception as e:
        print(f"[GYRO] Ошибка калибровки: {e}")

    print("[GYRO] Гироскоп готов. Начало интеграции угла Z.")
    gyro_sensor.get_angles(reset=True)  # сброс интегратора

    while not stop_event.is_set():
        try:
            angle_x, angle_y, angle_z = gyro_sensor.get_angles()
            # with open("log_coords_and_heading.txt", "a") as file:
            #                 file.write(f"angle_x:{angle_x}\t angle_y:{angle_y} angle_z:{angle_z}\n")
            # Z — вертикальная ось (рыскание / yaw)
            data_queue.put({'type': 'gyro_heading', 'value': angle_z})
            time.sleep(0.01)  # ~100 Гц
        except Exception as e:
            print(f"[GYRO] Ошибка: {e}")
            time.sleep(0.1)

# === HMI ===
def hmi_thread():
    print("\n[HMI] Команды:")
    #print("  target n x0 y0 ... xn yn — задать маршрут из n точек")
    print("  target filename — задать маршрут из файла")
    print("  start        — начать движение")
    print("  stop         — остановить")
    print("  quit         — выйти\n")
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
            elif cmd[0] == 'target':
                # if len(cmd) < 4:
                #     print("[HMI] Формат: target n x0 y0 ... xn yn")
                #     # target 6 6 3 7 3 8 2 7 1 6 1 5 2
                #     continue

                # try:
                with open(cmd[1], "r") as file:
                    waypoints = []
                    for waypoint in file.readlines():
                        print(waypoint)
                        x, y = waypoint.split()
                        waypoints.append((float(x), float(y)))
                waypoint_count = len(waypoints)
                    # waypoint_count = int(cmd[1])

                # except ValueError:
                #     print("[HMI] n должно быть целым числом")
                #     continue

                # if waypoint_count <= 0:
                #     print("[HMI] Количество точек должно быть больше 0")
                #     continue

                # expected_len = 2 + waypoint_count * 2
                # if len(cmd) != expected_len:
                #     print(f"[HMI] Ожидается {expected_len - 2} координат (n={waypoint_count})")
                #     continue

                # waypoints = []
                # try:
                #     for i in range(waypoint_count):
                #         x = float(cmd[2 + 2 * i])
                #         y = float(cmd[3 + 2 * i])
                #         waypoints.append((x, y))
                # except ValueError:
                #     print("[HMI] Координаты должны быть числами")
                #     continue

                data_queue.put({'type': 'targets', 'value': waypoints})
                print(f"[HMI] Принято {waypoint_count} точек")
            else:
                print("[HMI] Неизвестная команда")
        except (EOFError, KeyboardInterrupt):
            stop_event.set()
            break

# === MAIN ===
if __name__ == "__main__":
    # Файл логов
    with open("log_coords_and_heading.txt", "w") as file:
        file.write("")
        
    robot = gyro = None
    try:
        print("Инициализация робота...")
        robot = DifferentialDriveRobot(**ROBOT_PINS)

        print("Инициализация гироскопа...")
        gyro = GyroscopeClass(port=1, addr=0x68)

        threads = [
            threading.Thread(target=uwb_thread, daemon=True),
            threading.Thread(target=gyro_thread, args=(gyro,), daemon=True),
            threading.Thread(target=hmi_thread, daemon=True),
            threading.Thread(
                target=control_algorithm_thread,
                args=(data_queue, robot, stop_event),
                kwargs={
                    'linear_speed': 60,
                    'angular_speed': 40,
                    'angle_threshold': 5.0,
                    'stop_radius': 0.5
                },
                daemon=True
            ),
        ]

        for t in threads:
            t.start()

        print("\nСистема запущена (UWB + гироскоп)!\n")

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