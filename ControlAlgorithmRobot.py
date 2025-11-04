import time
import math
from collections import deque
from queue import Empty

def control_algorithm_thread(data_queue, robot, stop_event,
                             linear_speed=60,
                             angular_speed=40,
                             angle_threshold=5.0,      # градусов
                             stop_radius=0.5,          # метров или мм — зависит от UWB!
                             waypoint_mode=True):
    """
    Управление роботом по точкам с использованием UWB и гироскопа.
    
    Режим работы:
      1. Получить цель (x1, y1)
      2. Запомнить старт (x0, y0) = текущая позиция
      3. Вычислить желаемый курс
      4. Сбросить гироскоп
      5. Повернуться к цели (по гироскопу)
      6. Двигаться вперёд до достижения цели
    """

    current_pos = (0.0, 0.0)
    current_heading = 0.0  # градусы, от гироскопа (Z-ось)
    target_pos = None
    start_pos = None       # (x0, y0) — точка начала движения к цели
    waypoints = deque()

    state = 'IDLE'  # 'IDLE', 'ROTATING', 'MOVING'

    print("[CONTROL] Управление запущено (UWB + гироскоп)")

    def acquire_next_target():
        nonlocal target_pos, start_pos
        if not waypoints:
            return False
        target_pos = waypoints.popleft()
        start_pos = current_pos
        print(f"[CONTROL] Следующая цель: {target_pos} (осталось {len(waypoints)})")
        return True

    while not stop_event.is_set():
        with open("log_coords_and_heading.txt", "a") as file:
            file.write(f"{current_pos[0]} {current_pos[1]} {current_heading}\n")
        # --- Обработка входных данных ---
        while not data_queue.empty():
            try:
                msg = data_queue.get_nowait()
                #print("Попали в msg: ", msg)
                if msg['type'] == 'position':
                    current_pos = msg['value']
                elif msg['type'] == 'gyro_heading':
                    current_heading = msg['value']  # угол в градусах
                elif msg['type'] == 'command':
                    if msg['value'] == 'start':
                        if target_pos is None:
                            if not acquire_next_target():
                                print("[CONTROL] Нет цели для старта!")
                                continue
                        else:
                            start_pos = current_pos  # фиксируем старт!
                        state = 'ROTATING'
                        print(f"[CONTROL] Начало движения от {start_pos} к {target_pos}")
                    elif msg['value'] == 'stop':
                        state = 'IDLE'
                        robot.stop()
                        print("[CONTROL] Остановка по команде")
                elif msg['type'] == 'target':
                    waypoints.clear()
                    target_pos = msg['value']
                    print(f"[CONTROL] Новая цель: {target_pos}")
                    # Сброс состояния
                    state = 'IDLE'
                elif msg['type'] == 'targets':
                    print("Попали в targets")
                    waypoints.clear()
                    waypoints.extend(msg['value'])
                    print("Получено точек: ", waypoints)
                    target_pos = None
                    robot.stop()
                    if waypoints:
                        print(f"[CONTROL] Получен маршрут из {len(waypoints)} точек")
                    else:
                        print("[CONTROL] Пустой маршрут")
                    state = 'IDLE'

            except Empty:
                break

        # --- Логика состояний ---
        if state == 'ROTATING':
            if start_pos is None or target_pos is None:
                state = 'IDLE'
                continue

            x0, y0 = start_pos
            x1, y1 = target_pos
            dx = x1 - x0
            dy = y1 - y0

            if abs(dx) < 1e-6 and abs(dy) < 1e-6:
                print("[CONTROL] Цель совпадает со стартом!")
                state = 'IDLE'
                continue

            # Желаемый курс к цели (в градусах)
            target_angle = math.degrees(math.atan2(dy, dx)) % 360
            current_norm = current_heading % 360

            # Разница с нормализацией [-180, +180]
            delta = target_angle - current_norm
            if delta > 180:
                delta -= 360
            elif delta < -180:
                delta += 360

            print(f"[ROTATE] Цель: {target_angle:.1f}°, Текущий: {current_norm:.1f}°, Δ: {delta:.1f}°")

            if abs(delta) <= angle_threshold:
                print("[CONTROL] ✅ Поворот завершён. Начинаем движение.")
                # robot.stop()
                state = 'MOVING'
            else:
                # Поворот на месте
                if delta > 0:
                    robot.set_speed(-angular_speed, angular_speed)  # влево
                else:
                    robot.set_speed(angular_speed, -angular_speed)  # вправо

        elif state == 'MOVING':
            if target_pos is None:
                state = 'IDLE'
                continue

            # Расстояние до цели (не от start_pos, а от текущей позиции!)
            tx, ty = target_pos
            x, y = current_pos
            distance = math.hypot(tx - x, ty - y)

            print(f"[MOVE] Расстояние до цели: {distance:.3f}")

            if distance < stop_radius:
                robot.stop()
                print(f"[CONTROL] 🎯 Цель достигнута! ({tx:.1f}, {ty:.1f})")
                target_pos = None
                if acquire_next_target():
                    state = 'ROTATING'
                    print("[CONTROL] Продолжаем движение к следующей точке")
                else:
                    print("[CONTROL] ✅ Маршрут завершён")
                    state = 'IDLE'
            else:
                robot.set_speed(linear_speed, linear_speed)

        elif state == 'IDLE':
            robot.stop()

        time.sleep(0.02)  # ~50 Гц

    robot.stop()
    print("[CONTROL] Поток управления завершён")