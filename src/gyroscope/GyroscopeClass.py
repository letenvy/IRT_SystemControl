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