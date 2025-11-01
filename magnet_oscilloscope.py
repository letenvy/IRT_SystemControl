#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

# === КРИТИЧЕСКИ ВАЖНО: проверка и установка бэкенда ДО импорта matplotlib ===
if "DISPLAY" not in os.environ:
    print("❌ Переменная DISPLAY не установлена. Запустите через 'ssh -X'.")
    sys.exit(1)

# Принудительно используем TkAgg
import matplotlib
matplotlib.use('TkAgg')  # ← ЭТО ДОЛЖНО БЫТЬ ПЕРВЫМ ИМПОРТОМ, связанным с matplotlib

# Теперь можно импортировать pyplot
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
# ... остальные импорты
import threading
import numpy as np
import time
import sys

# Импортируем ваш класс магнитометра
# Убедитесь, что файл называется Magnit_Class_copy.py и лежит в той же папке
from Magnit_Class_copy import HMC5883L


def main():
    # === Настройки ===
    DURATION = 5.0           # Длина окна графика (сек)
    SAMPLE_RATE = 20         # Частота опроса датчика (Гц)
    UPDATE_INTERVAL_MS = int(1000 / 10)  # Частота обновления графика (10 Гц достаточно)

    print("🔍 Инициализация магнитометра...")
    try:
        compass = HMC5883L(gauss=4.7, declination=(7, 22))
        print("✅ Магнитометр готов.")
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")
        sys.exit(1)

    # === Буферы данных ===
    N = int(DURATION * SAMPLE_RATE)
    xs = np.zeros(N)
    ys = np.zeros(N)
    zs = np.zeros(N)
    running = True
    buffer_index = 0

    # === Поток чтения данных ===
    def read_sensor():
        nonlocal buffer_index
        while running:
            try:
                x, y, z = compass.read_data()
                if x is None or y is None or z is None:
                    x = y = z = 0
                # Циклическая запись
                xs[buffer_index] = x
                ys[buffer_index] = y
                zs[buffer_index] = z
                buffer_index = (buffer_index + 1) % N
                time.sleep(1.0 / SAMPLE_RATE)
            except Exception as e:
                print(f"[Поток] Ошибка: {e}")
                time.sleep(0.1)

    reader_thread = threading.Thread(target=read_sensor, daemon=True)
    reader_thread.start()
    print("📡 Поток чтения запущен.")

    # === Настройка графика ===
    plt.style.use('seaborn-v0_8')
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_title("Магнитометр HMC5883L — Осциллограф (X, Y, Z)", fontsize=12)
    ax.set_xlabel("Время (с)")
    ax.set_ylabel("Магнитное поле")
    ax.grid(True, linestyle='--', alpha=0.6)

    times = np.linspace(-DURATION, 0, N)
    line_x, = ax.plot(times, xs, label='X', color='red')
    line_y, = ax.plot(times, ys, label='Y', color='green')
    line_z, = ax.plot(times, zs, label='Z', color='blue')
    ax.legend(loc='upper right')
    ax.set_xlim(-DURATION, 0)
    ax.set_ylim(-8000, 8000)

    # === Обновление графика ===
    def update(frame):
        # Обновляем данные (буфер уже содержит последние N точек)
        line_x.set_ydata(xs)
        line_y.set_ydata(ys)
        line_z.set_ydata(zs)

        # Автоподстройка по Y (опционально)
        all_vals = np.concatenate([xs, ys, zs])
        if not np.all(all_vals == 0):
            ymin, ymax = np.min(all_vals), np.max(all_vals)
            margin = (ymax - ymin) * 0.1 or 200
            ax.set_ylim(ymin - margin, ymax + margin)

        return line_x, line_y, line_z

    # === Обработка закрытия окна ===
    def on_close(event):
        nonlocal running
        print("\nCloseOperation: остановка потока...")
        running = False
        plt.close(fig)

    fig.canvas.mpl_connect('close_event', on_close)

    print("📈 Запуск графика. Окно должно появиться на вашем компьютере...")
    ani = FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS, blit=False)
    plt.tight_layout()
    plt.show()

    print("✅ График закрыт. Выход.")


if __name__ == "__main__":
    main()