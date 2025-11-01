import time
import math
from collections import deque

def control_algorithm_thread(data_queue, robot, stop_event, 
                             linear_speed=60, angular_speed=50, stop_radius=50.0,
                             correction_interval=0.3):  # коррекция каждые 30 см
    # Текущие данные
    current_pos = (0.0, 0.0)
    current_compass = 0.0  # компас, [0, 360)
    target_pos = None

    # Абсолютный курс робота из UWB (после калибровки или коррекции)
    uwb_heading = None  # в градусах, математическая система: 0° = +X, +CCW

    # Состояния основного движения
    STATE_IDLE = 0
    STATE_ALIGN = 1          # подготовка к повороту
    STATE_ALIGN_ROTATING = 2 # поворот на месте с использованием компаса
    STATE_MOVE = 3        # движение к цели
    state = STATE_IDLE
    # Для ALIGN
    compass_zero = 0.0
    target_turn_angle = 0.0

    # Для MOVE
    move_start_pos = (0.0, 0.0)
    last_correction_pos = (0.0, 0.0)

    # === Состояния калибровки (оставляем как есть) ===
    CALIB_IDLE = 0
    CALIB_COLLECT_START = 1
    CALIB_MOVE_FORWARD = 2
    CALIB_COLLECT_END = 3
    CALIB_MOVE_BACK = 4
    CALIB_DONE = 5

    calib_state = CALIB_IDLE
    calib_start_time = 0.0
    calib_start_pos = (0.0, 0.0)
    calib_end_pos = (0.0, 0.0)
    calib_forward_duration = 2.0
    calib_collect_duration = 5.0
    calib_forward_speed = 30
    start_buffer = deque(maxlen=100)
    end_buffer = deque(maxlen=100)

    print("[CONTROL] Поток управления запущен")

    while not stop_event.is_set():
        # --- Обработка входящих сообщений ---
        while not data_queue.empty():
            try:
                msg = data_queue.get_nowait()
                msg_type = msg['type']
                value = msg['value']

                if msg_type == 'position':
                    current_pos = value
                elif msg_type == 'heading':
                    current_compass = value
                elif msg_type == 'target':
                    target_pos = value
                    print(f"[CONTROL] Новая цель: {target_pos}")
                elif msg_type == 'command':
                    if value == 'start':
                        if target_pos is not None and uwb_heading is not None:
                            state = STATE_ALIGN
                            print("[CONTROL] СТАРТ: вход в ALIGN")
                        else:
                            missing = []
                            if target_pos is None: missing.append("цель")
                            if uwb_heading is None: missing.append("калибровка")
                            print(f"[CONTROL] Нельзя стартовать: {', '.join(missing)}")
                    elif value == 'stop':
                        state = STATE_IDLE
                        robot.stop()
                        print("[CONTROL] СТОП")
                    elif value == 'calibrate1':
                        if calib_state == CALIB_IDLE:
                            calib_state = CALIB_COLLECT_START
                            calib_start_time = time.time()
                            start_buffer.clear()
                            print("[CALIB] Запуск калибровки: сбор начальной позиции")
                        else:
                            print("[CALIB] Калибровка уже запущена!")

            except Exception:
                break

        # --- Логика калибровки (неблокирующая) ---
        if calib_state != CALIB_IDLE:
            now = time.time()

            if calib_state == CALIB_COLLECT_START:
                start_buffer.append(current_pos)
                if now - calib_start_time >= calib_collect_duration:
                    n = len(start_buffer)
                    avg_x = sum(p[0] for p in start_buffer) / n
                    avg_y = sum(p[1] for p in start_buffer) / n
                    calib_start_pos = (avg_x, avg_y)
                    print(f"[CALIB] Начальная позиция: ({avg_x:.3f}, {avg_y:.3f})")
                    calib_state = CALIB_MOVE_FORWARD
                    calib_start_time = now
                    robot.set_speed(calib_forward_speed, calib_forward_speed)

            elif calib_state == CALIB_MOVE_FORWARD:
                if now - calib_start_time >= calib_forward_duration:
                    robot.stop()
                    calib_state = CALIB_COLLECT_END
                    calib_start_time = now
                    end_buffer.clear()
                    print("[CALIB] Сбор конечной позиции")

            elif calib_state == CALIB_COLLECT_END:
                end_buffer.append(current_pos)
                if now - calib_start_time >= calib_collect_duration:
                    n = len(end_buffer)
                    avg_x = sum(p[0] for p in end_buffer) / n
                    avg_y = sum(p[1] for p in end_buffer) / n
                    calib_end_pos = (avg_x, avg_y)
                    print(f"[CALIB] Конечная позиция: ({avg_x:.3f}, {avg_y:.3f})")

                    dx = calib_end_pos[0] - calib_start_pos[0]
                    dy = calib_end_pos[1] - calib_start_pos[1]
                    dist = math.hypot(dx, dy)
                    if dist < 0.1:
                        print("[CALIB] ⚠️ Робот почти не двигался!")
                        uwb_heading = None
                    else:
                        uwb_heading = math.degrees(math.atan2(dy, dx)) % 360
                        print(f"[CALIB] Установлен uwb_heading = {uwb_heading:.1f}°")

                    calib_state = CALIB_MOVE_BACK
                    calib_start_time = now
                    robot.set_speed(-calib_forward_speed, -calib_forward_speed)

            elif calib_state == CALIB_MOVE_BACK:
                if now - calib_start_time >= calib_forward_duration + 0.3:
                    robot.stop()
                    calib_state = CALIB_IDLE
                    print("[CALIB] ✅ Калибровка завершена.")

        # --- Логика движения (только если калибровка не активна) ---
        elif state != STATE_IDLE and target_pos is not None:
            x, y = current_pos
            tx, ty = target_pos
            dx = tx - x
            dy = ty - y
            distance = math.hypot(dx, dy)

            if distance < stop_radius:
                robot.stop()
                print(f"[CONTROL] 🎯 Цель достигнута! Расстояние: {distance:.1f}")
                state = STATE_IDLE
                continue

            if state == STATE_ALIGN:
                # Вычисляем, на сколько нужно повернуться
                target_angle = math.degrees(math.atan2(dy, dx)) % 360
                delta_global = target_angle - uwb_heading
                delta_global = (delta_global + 180) % 360 - 180  # [-180, 180]

                # Сбрасываем компас для измерения поворота
                compass_zero = current_compass
                target_turn_angle = delta_global
                print(f"[ALIGN] Нужно повернуться на {target_turn_angle:.1f}°")
                state = STATE_ALIGN_ROTATING

            elif state == STATE_ALIGN_ROTATING:
                # Измеряем поворот по компасу
                delta_compass = -(current_compass - compass_zero)
                delta_compass = (delta_compass + 180) % 360 - 180
                print(f"таргет = {target_turn_angle:.2f}, угол = {delta_compass:.2f}, текущий = current_heading = {current_compass:.2f}")

                if abs(delta_compass - target_turn_angle) < 2.0:
                    print(f"[ALIGN] Поворот завершён")
                    move_start_pos = current_pos
                    last_correction_pos = current_pos
                    uwb_heading = (uwb_heading + delta_compass) % 360
                    robot.stop()
                    state = STATE_MOVE
                    continue

                # Управление поворотом
                error = target_turn_angle - delta_compass
                robot.set_speed(-angular_speed, angular_speed)

                # if error > 0:
                #     robot.set_speed(-angular_speed, angular_speed)
                # else:
                #     robot.set_speed(angular_speed, -angular_speed)

            elif state == STATE_MOVE:
                # Проверка на коррекцию
                dist_since_corr = math.hypot(
                    current_pos[0] - last_correction_pos[0],
                    current_pos[1] - last_correction_pos[1]
                )

                if dist_since_corr >= correction_interval:
                    # Обновляем uwb_heading по фактическому движению
                    move_dx = current_pos[0] - move_start_pos[0]
                    move_dy = current_pos[1] - move_start_pos[1]
                    # if move_dx**2 + move_dy**2 > 0.01:
                    #     uwb_heading = math.degrees(math.atan2(move_dy, move_dx)) % 360

                    # Проверяем, смотрим ли мы в цель
                    target_angle = math.degrees(math.atan2(dy, dx)) % 360
                    delta_check = target_angle - uwb_heading
                    delta_check = (delta_check + 180) % 360 - 180

                    if abs(delta_check) > 10.0:
                        print(f"[CORRECT] Отклонение {delta_check:.1f}° — повтор ALIGN")
                        robot.stop()
                        state = STATE_ALIGN
                        continue

                    last_correction_pos = current_pos

                robot.set_speed(linear_speed, linear_speed)

        else:
            robot.stop()

        time.sleep(0.02)

    robot.stop()
    print("[CONTROL] Поток управления завершён")