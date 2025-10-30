# control_algorithm.py

import time
import math
from queue import Empty
from Magnit_Class import HMC5883L
def control_algorithm_thread(data_queue, robot, stop_event, 
                             linear_speed=60, angular_speed=50, stop_radius=50.0):
    """
    Поток управления роботом на основе данных из очереди.
    
    Параметры:
        data_queue: queue.Queue — входные данные от UWB, MAG, HMI
        robot: DifferentialDriveRobot — объект управления моторами
        stop_event: threading.Event — сигнал завершения
        linear_speed, angular_speed, stop_radius — параметры управления
    """
    current_pos = (0.0, 0.0)
    current_heading = 0.0
    target_pos = None
    running = False
    calibrate = False

    print("[CONTROL] Поток управления запущен")

    while not stop_event.is_set():
        # Обработка всех новых сообщений из очереди
        while not data_queue.empty():
            try:
                msg = data_queue.get_nowait()
                msg_type = msg['type']
                value = msg['value']

                if msg_type == 'position':
                    current_pos = value
                elif msg_type == 'heading':
                    current_heading = value
                elif msg_type == 'target':
                    target_pos = value
                    print(f"[CONTROL] Новая цель: {target_pos}")
                elif msg_type == 'command':
                    if value == 'start':
                        if target_pos is not None:
                            running = True
                            print("[CONTROL] Команда: СТАРТ")
                        else:
                            print("[CONTROL] Нельзя стартовать без цели!")
                    elif value == 'stop':
                        running = False
                        robot.stop()
                        print("[CONTROL] Команда: СТОП")
                    elif value == 'calibrate':
                        calibrate = True

            except Empty:
                break


        # Калибровка
        #if calibrate:
            # mx_values = []
            # my_values = []
            # robot.set_speed(-angular_speed, angular_speed) #жоска крутится
            # duration = time.time() + 10 #время записи значений для калибровки
            # while time.time() < duration:
            #     x, y, _ = compas.read_data()
            #     mx_values.append(x)
            #     my_values.append(y)
            #     time.sleep(0.05)

            # # === Min-Max калибровка (только X и Y) === жоские формулы
            # min_x, max_x = min(mx_values), max(mx_values)
            # min_y, max_y = min(my_values), max(my_values)

            # bias_x = (max_x + min_x) / 2.0 #смещение
            # bias_y = (max_y + min_y) / 2.0

            # range_x = max_x - min_x
            # range_y = max_y - min_y

            # if range_x == 0 or range_y == 0:
            #     raise ValueError("[Калибровка] Диапазон измерений нулевой — Лохи, проверьте подключение магнитометра!")

            # # Средний радиус (по полуразмахам)
            # avg_radius = (range_x + range_y) / 4.0

            # scale_x = avg_radius / (range_x / 2.0)
            # scale_y = avg_radius / (range_y / 2.0)

            # calibrate = False
            # compas.set_calibration(bias_x, bias_y, scale_x, scale_y)
            # compas.save_calibration()
            # robot.stop()
            # print("\n=== Результаты калибровки ===")
            # print(f"Смещение (bias):  X = {bias_x:.2f}, Y = {bias_y:.2f}")
            # print(f"Масштаб (scale): X = {scale_x:.4f}, Y = {scale_y:.4f}")
            # print(f"Собрано точек: {len(mx_values)} за {CALIBRATION_DURATION} сек")
            # print("============================\n")



        # Логика движения
        if running and target_pos is not None:

            x, y = current_pos
            tx, ty = target_pos
            dx = tx - x
            dy = ty - y
            distance = math.hypot(dx, dy)

            if distance < stop_radius:
                robot.stop()
                print(f"[CONTROL] 🎯 Цель достигнута! Расстояние: {distance:.1f}")
                running = False  # автоматическая остановка
                continue

            # Желаемый угол к цели
            target_angle_deg = math.degrees(math.atan2(dy, dx)) % 360
            current_heading_norm = (current_heading - 233) % 360 # ДОБАВИЛИ -233 ГРАДУСОВ !!!!!
            angle_diff = target_angle_deg - current_heading_norm
            #print('наша позиция', current_pos)
            #print(f"угол = {angle_diff:.2f}, таргет = {target_angle_deg:.2f}, текущий = {current_heading_norm:.2f} current_heading = {current_heading:.2f}")

            # Нормализация к [-180, +180]
            if angle_diff > 180:
                angle_diff -= 360
            elif angle_diff < -180:
                angle_diff += 360

            angle_threshold = 10.0

            # Управление
            # if abs(angle_diff) > angle_threshold:
            #     if angle_diff > 0:
            #         robot.set_speed(-angular_speed, angular_speed)  # поворот влево
            #     else:
            #         robot.set_speed(angular_speed, -angular_speed)  # поворот вправо
            # else:
            #     robot.set_speed(linear_speed, linear_speed)  # движение вперёд

        time.sleep(0.05)  # ~20 Гц

    robot.stop()
    print("[CONTROL] Поток управления завершён")
