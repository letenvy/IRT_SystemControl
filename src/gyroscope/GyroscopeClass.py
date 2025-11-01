import sys
import os
# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from .i2c_itg3205 import i2c_itg3205
import time
import json
import csv
import threading


class GyroscopeClass:
    def __init__(self, port=1, addr=0x68):
        self.gyro = i2c_itg3205(port=port, addr=addr)
        self.stop_flag = False

    def read_once(self):
        return self.gyro.getDegPerSecAxes()

    def log_to_json(self, filename="gyro_log.json"):
        print("Логирование в JSON. Нажмите Enter для остановки...")
        self._run_logging(
            on_start=lambda: [],
            on_data=lambda data, log: log.append(data),
            on_stop=lambda log, _: self._save_json(log, filename),
            filename=filename
        )

    def log_to_csv(self, filename="gyro_log.csv"):
        print("Логирование в CSV. Нажмите Enter для остановки...")
        def on_start():
            f = open(filename, 'w', newline='', buffering=1)
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'x', 'y', 'z'])
            return (f, writer)

        def on_data(data, context):
            f, writer = context
            writer.writerow([data['timestamp'], data['x'], data['y'], data['z']])

        def on_stop(context, _):
            f, _ = context
            f.close()

        self._run_logging(
            on_start=on_start,
            on_data=on_data,
            on_stop=on_stop,
            filename=filename
        )

    def _save_json(self, data, filename):
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

    def _run_logging(self, on_start, on_data, on_stop, filename):
        self.stop_flag = False

        def wait_for_enter():
            input()
            self.stop_flag = True

        thread = threading.Thread(target=wait_for_enter, daemon=True)
        thread.start()

        log_context = on_start()
        last_time = time.time()
        interval_sum = 0
        interval_count = 0
        hz = 0.0

        try:
            while not self.stop_flag:
                start = time.time()
                x, y, z = self.read_once()
                ts = time.time()

                dt = start - last_time
                last_time = start
                if dt > 0:
                    interval_sum += dt
                    interval_count += 1
                    if interval_count >= 10:
                        hz = round(10 / interval_sum, 1)
                        interval_sum = 0
                        interval_count = 0

                print(f"\rX={x:7.2f}, Y={y:7.2f}, Z={z:7.2f} | Hz: {hz:4.1f}", end='', flush=True)

                data = {"timestamp": ts, "x": x, "y": y, "z": z}
                on_data(data, log_context)

                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\nПрервано пользователем.")
        finally:
            on_stop(log_context, None)
            print(f"\n\nЛог завершён. Файл: {filename}")

    def calibrate_bias(self, samples=100):
        sx = sy = sz = 0
        for _ in range(samples):
            x, y, z = self.read_once()
            sx += x; sy += y; sz += z
            time.sleep(0.01)
        self.bias_x = sx / samples
        self.bias_y = sy / samples
        self.bias_z = sz / samples

    def read_corrected(self):
        x, y, z = self.read_once()
        return x - self.bias_x, y - self.bias_y, z - self.bias_z

    def get_angles(self, dt=None,reset=False):

        current_time=time.time()

        if not hasattr(self, '_angle_x'):
            self._angle_x = self._angle_y = self._angle_z = 0.0
            self._last_time = current_time

            self.read_once()
            return (0.0, 0.0, 0.0)
    
        if dt is None:
            dt = current_time - self._last_time
            self._last_time = current_time

        if dt <= 0:
            return (self._angle_x, self._angle_y, self._angle_z)

        wx, wy, wz = self.read_once()
        self._angle_x += wx * dt
        self._angle_y += wy * dt
        self._angle_z += wz * dt

        return (self._angle_x, self._angle_y, self._angle_z)

    def calibrate_and_save(self,filename="gyro_bias.json",samples=200,delay=0.01):
        print(f"Калибровка гироскопа ({samples} измерений). Убедитесь, что устройство НЕПОДВИЖНО!")
        time.sleep(1)

        sum_x = sum_y = sum_z = 0.0
        for i in range(samples):
            x, y, z = self.read_once()
            sum_x += x
            sum_y += y
            sum_z += z
            if i % 20 == 0:
                print(f"\rПрогресс: {i}/{samples}", end='', flush=True)
            time.sleep(delay)

        bias_x = sum_x / samples
        bias_y = sum_y / samples
        bias_z = sum_z / samples

        bias_data = {
            "bias_x": bias_x,
            "bias_y": bias_y,
            "bias_z": bias_z,
            "samples": samples,
            "timestamp": time.time()
        }

        with open(filename, 'w') as f:
            json.dump(bias_data, f, indent=2)
        
        print(f"\nКалибровка завершена. Bias сохранён в {filename}")
        print(f"X: {bias_x:.3f}, Y: {bias_y:.3f}, Z: {bias_z:.3f} град/с")
        return bias_x,bias_y,bias_z



    def track_angles(self,log_to_file=False,filename="gyro_angles_log.csv"):
        print("Отслеживание углов по гироскопу. Нажмите Enter для остановки...")

        self.get_angles(reset=True)
        log_file = None
        csv_writer = None
        if log_to_file:
            log_file = open(filename, 'w', newline='', buffering=1)
            csv_writer = csv.writer(log_file)
            csv_writer.writerow(['timestamp', 'angle_x', 'angle_y', 'angle_z'])

        self.stop_flag = False

        def wait_for_enter():
            input()
            self.stop_flag = True

        thread = threading.Thread(target=wait_for_enter, daemon=True)
        thread.start()

        hz = 0.0
        interval_sum = 0.0
        interval_count = 0
        last_print_time = time.time()

        try:
            while not self.stop_flag:
                # Получаем углы — интеграция внутри get_angles
                angle_x, angle_y, angle_z = self.get_angles()  # dt измеряется автоматически
                ts = time.time()

                # Логирование
                if log_to_file:
                    csv_writer.writerow([ts, angle_x, angle_y, angle_z])

                # Подсчёт частоты вывода (не обновления!)
                now = time.time()
                dt_print = now - last_print_time
                if dt_print > 0:
                    interval_sum += dt_print
                    interval_count += 1
                    if interval_count >= 10:
                        hz = round(10 / interval_sum, 1)
                        interval_sum = 0
                        interval_count = 0
                    last_print_time = now

                # Вывод одной строкой
                print(f"\rX={angle_x:8.2f}°, Y={angle_y:8.2f}°, Z={angle_z:8.2f}° | Hz: {hz:4.1f}", end='', flush=True)

                time.sleep(0.005)

        except KeyboardInterrupt:
            print("\nПрервано пользователем.")
        finally:
            if log_file:
                log_file.close()
            print(f"\n\nОтслеживание завершено. {'Лог сохранён в ' + filename if log_to_file else ''}")