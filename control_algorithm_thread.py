# control_algorithm_thread.py

import time
import math
import os

def clear_console():
    """Очистка консоли (работает на Linux и Windows)"""
    os.system('cls' if os.name == 'nt' else 'clear')

def control_algorithm_thread(data_queue, robot, stop_event,
                             linear_speed=60, angular_speed=80, stop_radius=0.1):
    """
    Поток управления с отладочным выводом и опциональным виртуальным курсом.
    """
    current_pos = (0.0, 0.0)
    current_heading_real = 0.0      # от магнитометра
    current_heading_virtual = 0.0   # рассчитанный (dead reckoning)
    use_virtual_heading = True      # ← переключатель: True = использовать виртуальный курс

    target_pos = None
    running = False
    start_time = None

    heading_buffer = []
    HEADING_BUFFER_SIZE = 5

    Kp = 0.8
    TURN_THRESHOLD = 30.0

    print("[CONTROL] Поток управления запущен")
    print(f"[CONTROL] Используется {'виртуальный курс' if use_virtual_heading else 'магнитометр'}")
    print("-" * 70)

    loop_count = 0

    while not stop_event.is_set():
        # Обработка сообщений
        while not data_queue.empty():
            try:
                msg = data_queue.get_nowait()
                if msg['type'] == 'position':
                    current_pos = msg['value']
                elif msg['type'] == 'heading':
                    current_heading_real = msg['value']
                elif msg['type'] == 'target':
                    target_pos = msg['value']
                    print(f"\n[🎯] Новая цель: {target_pos}")
                    start_time = None  # сброс таймера
                elif msg['type'] == 'command':
                    if msg['value'] == 'start':
                        if target_pos is not None:
                            running = True
                            start_time = time.time()
                            print(f"\n[🚀] СТАРТ! Цель: {target_pos}")
                        else:
                            print("\n[⚠️] Нельзя стартовать без цели!")
                    elif msg['value'] == 'stop':
                        running = False
                        robot.stop()
                        print("\n[🛑] СТОП по команде")
            except:
                break

        # === Фильтрация реального курса ===
        heading_buffer.append(current_heading_real)
        if len(heading_buffer) > HEADING_BUFFER_SIZE:
            heading_buffer.pop(0)
        filtered_heading = sum(heading_buffer) / len(heading_buffer)

        # === Выбор курса для управления ===
        if use_virtual_heading:
            # ПОКА что виртуальный курс = реальный при старте
            # (в будущем можно обновлять его на основе команд поворота)
            current_heading_for_control = current_heading_virtual
        else:
            current_heading_for_control = filtered_heading

        # === Управление ===
        if running and target_pos is not None:
            x, y = current_pos
            tx, ty = target_pos
            dx, dy = tx - x, ty - y
            distance = math.hypot(dx, dy)

            if distance <= stop_radius:
                robot.stop()
                elapsed = time.time() - start_time if start_time else 0
                print(f"\n[✅] Цель достигнута! Расстояние: {distance:.3f} м, Время: {elapsed:.1f} с")
                running = False
                start_time = None
            else:
                # Вычисление угла цели (азимут: 0°=север, + по ЧС)
                target_angle_deg = (math.degrees(math.atan2(dx, dy)) + 360) % 360.0
                current_hdg = current_heading_for_control % 360.0

                angle_diff = target_angle_deg - current_hdg
                while angle_diff > 180:
                    angle_diff -= 360
                while angle_diff < -180:
                    angle_diff += 360

                # Простая логика управления (можно заменить на robot.go_to_point позже)
                if abs(angle_diff) > TURN_THRESHOLD:
                    direction = 1 if angle_diff > 0 else -1
                    robot.set_speed(-angular_speed * direction, angular_speed * direction)
                else:
                    correction = Kp * angle_diff
                    left = linear_speed - correction
                    right = linear_speed + correction
                    left = max(-100, min(100, left))
                    right = max(-100, min(100, right))
                    robot.set_speed(left, right)

                # === Отладочный вывод ===
                loop_count += 1
                elapsed = time.time() - start_time if start_time else 0

                print(
                    f"[{loop_count:3d}] "
                    f"Позиция: ({x:6.3f}, {y:6.3f}) | "
                    f"Азимут: реал={filtered_heading:6.1f}°, вирт={current_heading_virtual:6.1f}° | "
                    f"Цель: {target_angle_deg:6.1f}° | "
                    f"Ошибка: {angle_diff:6.1f}° | "
                    f"Дист: {distance:5.3f} м | "
                    f"Время: {elapsed:4.1f} с"
                )

                # Очистка консоли каждые 5 строк
                if loop_count % 5 == 0:
                    time.sleep(0.1)  # дать прочитать последнюю строку
                    clear_console()
                    print(f"[CONTROL] Используется {'виртуальный курс' if use_virtual_heading else 'магнитометр'}")
                    print("-" * 70)

        time.sleep(0.05)

    robot.stop()
    print("\n[CONTROL] Поток завершён")