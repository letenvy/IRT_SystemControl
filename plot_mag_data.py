if __name__ == "__main__":
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    import threading
    import numpy as np
    from Magnit_Class_copy import HMC5883L
    import time

    #import matplotlib
    #print("Matplotlib backend:", matplotlib.get_backend())
    
    # === Настройки ===
    DURATION = 10.0          # Длина окна графика в секундах (например, 10 сек)
    SAMPLE_RATE = 100         # Гц (опрос каждые 1/50 = 0.02 сек)
    #UPDATE_INTERVAL_MS = 10
    UPDATE_INTERVAL_MS = int(100 / SAMPLE_RATE)  # интервал обновления анимации

    # Инициализация магнитометра
    compass = HMC5883L(gauss=4.7, declination=(7, 22))

    # Буферы: используем numpy для эффективности
    N = int(DURATION * SAMPLE_RATE)
    times = np.linspace(-DURATION, 0, N)  # начальное окно: от -10 до 0 сек
    xs = np.zeros(N)
    ys = np.zeros(N)
    zs = np.zeros(N)

    # Флаг для потока
    running = True

    # Функция опроса датчика в отдельном потоке
    def read_sensor():
        global running
        i = 0
        while running:
            try:
                x, y, z = compass.read_data()
                # Циклическая запись в буфер
                xs[i] = x if x is not None else 0
                ys[i] = y if y is not None else 0
                zs[i] = z if z is not None else 0
                i = (i + 1) % N
                time.sleep(1.0 / SAMPLE_RATE)
            except Exception as e:
                print(f"[Ошибка чтения] {e}")
                time.sleep(0.1)

    # Запуск потока
    reader_thread = threading.Thread(target=read_sensor, daemon=True)
    reader_thread.start()

    # === Настройка графика ===
    plt.style.use('seaborn-v0_8')
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_title("Магнитометр HMC5883L — Осциллограф (X, Y, Z)", fontsize=14)
    ax.set_xlabel("Время (с)", fontsize=12)
    ax.set_ylabel("Магнитное поле (условные единицы)", fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.6)

    line_x, = ax.plot(times, xs, label='X', color='red', linewidth=1.2)
    line_y, = ax.plot(times, ys, label='Y', color='green', linewidth=1.2)
    line_z, = ax.plot(times, zs, label='Z', color='blue', linewidth=1.2)
    ax.legend(loc='upper right')

    # Инициализация осей
    def init():
        ax.set_xlim(-DURATION, 0)
        # Начальный диапазон Y — можно подстроить позже
        ax.set_ylim(-8000, 8000)
        return line_x, line_y, line_z

    # Обновление графика
    def update(frame):
        # Сдвиг времени: текущий момент = 0, окно = [-DURATION, 0]
        # Буфер уже содержит последние N точек, но в циклическом порядке
        # Нужно "развернуть" его так, чтобы последняя записанная точка была в конце

        # Определяем, где "голова" буфера (последняя запись)
        # Но проще: просто обновляем всё — matplotlib сам отрисует
        line_x.set_ydata(xs)
        line_y.set_ydata(ys)
        line_z.set_ydata(zs)

        # Автоподстройка Y (опционально — можно закомментировать для стабильности)
        all_vals = np.concatenate([xs, ys, zs])
        if len(all_vals) > 0 and not np.all(all_vals == 0):
            ymin, ymax = np.min(all_vals), np.max(all_vals)
            margin = (ymax - ymin) * 0.1 or 200
            ax.set_ylim(ymin - margin, ymax + margin)

        return line_x, line_y, line_z

    # Анимация
    ani = FuncAnimation(
        fig,
        update,
        init_func=init,
        interval=UPDATE_INTERVAL_MS,
        blit=False,
        cache_frame_data=False
    )

    # Обработка закрытия окна
    def on_close(event):
        global running
        running = False
        print("Остановка потока чтения...")
    fig.canvas.mpl_connect('close_event', on_close)

    plt.tight_layout()
    plt.show()

    # После закрытия окна — дожидаемся завершения потока (опционально)
    running = False
