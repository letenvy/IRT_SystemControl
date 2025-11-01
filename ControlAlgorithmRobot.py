# control_algorithm.py

import time
import math
from queue import Empty
from Magnit_Class import HMC5883L

def average_uwb_position(curent_position, duration_sec=5.0, interval=0.1):
    """Собирает UWB-позиции в течение duration_sec и возвращает усреднённую."""
    positions = []
    start = time.time()
    while time.time() - start < duration_sec:
        try:
            pos = curent_position  # ДОЛЖНА ВОЗВРАЩАТЬ (x, y)
            if pos is not None:
                positions.append(pos)
        except Exception as e:
            print(f"[UWB] Ошибка: {e}")
        time.sleep(interval)

    if not positions:
        raise RuntimeError("Не удалось получить UWB-данные")

    avg_x = sum(p[0] for p in positions) / len(positions)
    avg_y = sum(p[1] for p in positions) / len(positions)
    return (avg_x, avg_y)


def calibrate_heading_and_return(robot, curent_position, forward_speed=20, forward_time=2.0):
    """
    Калибрует направление робота по UWB и возвращает его на исходную точку.
    
    Параметры:
        robot — объект с методами set_speed(l, r) и stop()
        forward_speed — скорость в условных единицах (например, 20 из 100)
        forward_time — сколько секунд ехать вперёд
    """
    print("[CALIB] Шаг 1: Сбор начальной позиции (5 сек)...")
    start_pos = average_uwb_position(duration_sec=5.0)
    print(f"[CALIB] Начальная позиция: ({start_pos[0]:.3f}, {start_pos[1]:.3f})")

    # Едем вперёд
    print(f"[CALIB] Шаг 2: Едем вперёд {forward_time} сек со скоростью {forward_speed}...")
    robot.set_speed(forward_speed, forward_speed)
    time.sleep(forward_time)
    robot.stop()

    # Ждём, пока робот остановится и UWB стабилизируется
    time.sleep(0.5)

    print("[CALIB] Шаг 3: Сбор конечной позиции (5 сек)...")
    end_pos = average_uwb_position(duration_sec=5.0)
    print(f"[CALIB] Конечная позиция: ({end_pos[0]:.3f}, {end_pos[1]:.3f})")

    # Вычисляем вектор движения
    dx = end_pos[0] - start_pos[0]
    dy = end_pos[1] - start_pos[1]
    distance_moved = math.hypot(dx, dy)

    if distance_moved < 0.1:
        raise RuntimeError("Робот почти не переместился — проверьте UWB и движение!")

    print(f"[CALIB] Пройдено: {distance_moved:.3f} м")

    # Вычисляем угол движения в глобальной системе (математический, от +X против ЧС)
    movement_angle_rad = math.atan2(dy, dx)
    movement_angle_deg = math.degrees(movement_angle_rad) % 360
    print(f"[CALIB] Направление движения: {movement_angle_deg:.1f}° (от +X против ЧС)")

    # === Возврат назад ===
    print("[CALIB] Шаг 4: Возвращаемся назад на исходную позицию...")
    # Едем задом с той же скоростью
    robot.set_speed(-forward_speed, -forward_speed)
    time.sleep(forward_time + 0.2)  # чуть дольше на всякий случай
    robot.stop()

    # Финальная проверка
    print("[CALIB] Шаг 5: Проверка финальной позиции...")
    final_pos = average_uwb_position(duration_sec=3.0)
    final_dist = math.hypot(final_pos[0] - start_pos[0], final_pos[1] - start_pos[1])
    print(f"[CALIB] Отклонение от старта: {final_dist:.3f} м")

    if final_dist > 0.15:
        print("[WARN] Робот не вернулся точно — возможно, проскальзывание или неточность UWB")
    else:
        print("[CALIB] ✅ Калибровка завершена успешно!")

    return {
        "start": start_pos,
        "end": end_pos,
        "movement_angle_deg": movement_angle_deg,
        "distance_moved": distance_moved,
        "final_error": final_dist
    }
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
                    elif value == 'calibrate1':
                        calibrate1 = True

            except Empty:
                break



        if calibrate1:
            calibrate_heading_and_return(robot, current_pos)

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
            target_angle_deg = (math.degrees(math.atan2(dx, dy)) + 360) % 360
            delta = target_angle_deg - current_heading
            delta = (delta + 180) % 360 - 180
            #print('наша позиция', current_pos)

            # Нормализация к [-180, +180]
            # if delta > 180:
            #     delta -= 360
            # elif delta < -180:
            #     delta += 360

            angle_threshold = 20.0
            print(f"угол = {delta:.2f}, таргет = {target_angle_deg:.2f}, текущий = current_heading = {current_heading:.2f}")

            # Управление
            # if abs(delta) > angle_threshold:
            #     if delta > 0:
            #         robot.set_speed(-angular_speed, angular_speed)  # поворот влево
            #     else:
            #         robot.set_speed(angular_speed, -angular_speed)  # поворот вправо
            # else:
            #     robot.set_speed(linear_speed, linear_speed)  # движение вперёд

        time.sleep(0.05)  # ~20 Гц




    robot.stop()
    print("[CONTROL] Поток управления завершён")
