# control_algorithm_thread.py

import time
import math
import csv
import os

def control_algorithm_thread(data_queue, robot, stop_event,
                             linear_speed=60, angular_speed=80, stop_radius=0.1):
    """
    Управление с ПД-регулятором по углу и записью лога в CSV.
    """
    current_pos = (0.0, 0.0)
    current_heading = 0.0
    target_pos = None
    running = False
    start_time = None

    # ПД параметры
    Kp = 0.5
    Kd = 0.05

    # Состояние ПД
    prev_error = 0.0
    last_time = time.time()

    # Фильтрация через sin/cos
    sin_buffer = []
    cos_buffer = []
    HEADING_BUFFER_SIZE = 8

    # === Настройки логирования ===
    LOG_ENABLED = True
    LOG_FILE = "pd_control_log.csv"

    # Инициализация CSV-файла
    log_file_handle = None
    csv_writer = None
    if LOG_ENABLED:
        # Уникальное имя, если файл уже существует
        base, ext = os.path.splitext(LOG_FILE)
        counter = 1
        log_path = LOG_FILE
        while os.path.exists(log_path):
            log_path = f"{base}_{counter}{ext}"
            counter += 1

        log_file_handle = open(log_path, mode='w', newline='', encoding='utf-8')
        csv_writer = csv.writer(log_file_handle)
        # Запись заголовка
        csv_writer.writerow([
            "timestamp", "elapsed", "x", "y", "raw_heading", "filtered_heading",
            "target_angle", "angle_error", "P", "D", "correction",
            "left_speed", "right_speed", "distance_to_target"
        ])
        print(f"[LOG] Запись в файл: {log_path}")

    print("[CONTROL] Запущен. Введите 'target x y', затем 'start'.")
    
    try:
        while not stop_event.is_set():
            # Обработка очереди
            while not data_queue.empty():
                try:
                    msg = data_queue.get_nowait()
                    if msg['type'] == 'position':
                        current_pos = msg['value']
                    elif msg['type'] == 'heading':
                        current_heading = msg['value']
                    elif msg['type'] == 'target':
                        target_pos = msg['value']
                        print(f"\n🎯 Новая цель: {target_pos}")
                        start_time = None
                    elif msg['type'] == 'command':
                        if msg['value'] == 'start':
                            if target_pos is not None:
                                running = True
                                start_time = time.time()
                                prev_error = 0.0
                                last_time = time.time()
                                sin_buffer.clear()
                                cos_buffer.clear()
                                print("\n🚀 СТАРТ")
                            else:
                                print("\n⚠️ Цель не задана!")
                        elif msg['value'] == 'stop':
                            running = False
                            robot.stop()
                            print("\n🛑 СТОП")
                except:
                    break

            if not running or target_pos is None:
                robot.stop()
                time.sleep(0.05)
                continue

            # === Фильтрация курса ===
            rad = math.radians(current_heading)
            sin_buffer.append(math.sin(rad))
            cos_buffer.append(math.cos(rad))
            if len(sin_buffer) > HEADING_BUFFER_SIZE:
                sin_buffer.pop(0)
                cos_buffer.pop(0)

            avg_sin = sum(sin_buffer) / len(sin_buffer)
            avg_cos = sum(cos_buffer) / len(cos_buffer)
            filtered_heading = math.degrees(math.atan2(avg_sin, avg_cos)) % 360.0

            x, y = current_pos
            tx, ty = target_pos
            distance = math.hypot(tx - x, ty - y)

            if distance <= stop_radius:
                robot.stop()
                elapsed = time.time() - start_time if start_time else 0
                print(f"\n✅ Цель достигнута! Время: {elapsed:.1f} с")
                running = False
                continue

            # === Расчёт угла цели ===
            target_angle = (math.degrees(math.atan2(tx - x, ty - y)) + 360) % 360.0
            current_hdg = filtered_heading

            angle_error = target_angle - current_hdg
            if angle_error > 180:
                angle_error -= 360
            elif angle_error < -180:
                angle_error += 360

            DEADBAND = 4.0
            if abs(angle_error) <= DEADBAND:
                robot.set_speed(linear_speed, linear_speed)
                elapsed = time.time() - start_time if start_time else 0
                timestamp = time.time()

                # Логирование
                if LOG_ENABLED and csv_writer:
                    csv_writer.writerow([
                        f"{timestamp:.3f}", f"{elapsed:.3f}",
                        f"{x:.3f}", f"{y:.3f}",
                        f"{current_heading:.2f}", f"{filtered_heading:.2f}",
                        f"{target_angle:.2f}", f"{angle_error:.2f}",
                        "0.0", "0.0", "0.0",
                        f"{linear_speed:.1f}", f"{linear_speed:.1f}",
                        f"{distance:.3f}"
                    ])
                    log_file_handle.flush()  # немедленная запись на диск

                print(f"\rx={x:.3f} y={y:.3f} hdg={current_hdg:6.1f}° tgt={target_angle:6.1f}° err={angle_error:6.1f}° dist={distance:.3f}m t={elapsed:.1f}s", end='', flush=True)
                time.sleep(0.02)
                continue

            # === ПД-регулятор ===
            now = time.time()
            dt = now - last_time
            if dt <= 0 or dt > 0.1:
                dt = 0.02

            P = Kp * angle_error
            derivative = (angle_error - prev_error) / dt
            derivative = max(-100.0, min(100.0, derivative))
            D = Kd * derivative
            correction = P + D
            correction = max(-45, min(45, correction))

            if abs(angle_error) > 25.0:
                left_speed = -correction
                right_speed = correction
            else:
                left_speed = linear_speed - correction
                right_speed = linear_speed + correction
                mx = max(abs(left_speed), abs(right_speed))
                if mx > 100:
                    scale = 100.0 / mx
                    left_speed *= scale
                    right_speed *= scale

            robot.set_speed(left_speed, right_speed)

            # Обновление состояния
            prev_error = angle_error
            last_time = now

            # === Запись в лог ===
            elapsed = time.time() - start_time if start_time else 0
            timestamp = time.time()
            if LOG_ENABLED and csv_writer:
                csv_writer.writerow([
                    f"{timestamp:.3f}", f"{elapsed:.3f}",
                    f"{x:.3f}", f"{y:.3f}",
                    f"{current_heading:.2f}", f"{filtered_heading:.2f}",
                    f"{target_angle:.2f}", f"{angle_error:.2f}",
                    f"{P:.2f}", f"{D:.2f}", f"{correction:.2f}",
                    f"{left_speed:.1f}", f"{right_speed:.1f}",
                    f"{distance:.3f}"
                ])
                log_file_handle.flush()

            # Вывод в консоль
            print(f"\rx={x:.3f} y={y:.3f} hdg={current_hdg:6.1f}° tgt={target_angle:6.1f}° err={angle_error:6.1f}° dist={distance:.3f}m t={elapsed:.1f}s", end='', flush=True)

            time.sleep(0.02)

    except KeyboardInterrupt:
        pass
    finally:
        robot.stop()
        if LOG_ENABLED and log_file_handle:
            log_file_handle.close()
        print("\n\n[CONTROL] Завершён.")