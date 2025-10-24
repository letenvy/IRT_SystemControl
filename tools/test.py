import os
import mmap
import tempfile
import numpy as np
import cv2
import time

# Параметры кадра
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
CHANNELS = 3
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * CHANNELS

# Используем временную директорию, подходящую для текущей ОС
temp_dir = tempfile.gettempdir()
SHM_FILENAMES = [os.path.join(temp_dir, "shm_frame0"), os.path.join(temp_dir, "shm_frame1")]


def get_mmap_buffer(filename, size):
    # Если файла нет – создаём и заполняем нулями
    if not os.path.exists(filename):
        with open(filename, "wb") as f:
            f.write(b'\x00' * size)
        print(f"Файл {filename} создан")
    # Открываем файл для чтения/записи
    fd = os.open(filename, os.O_RDWR)
    mm = mmap.mmap(fd, size)
    os.close(fd)
    return mm


# Получаем список "буферов" – маппинг файлов
shm_buffers = [get_mmap_buffer(fname, FRAME_SIZE) for fname in SHM_FILENAMES]

# Пример простого цикла, который читает данные из первого буфера
latest_index = 0
frame_count = 0
while True:
    buf = shm_buffers[latest_index]
    buf.seek(0)  # перемещаем указатель в начало
    frame_data = buf.read(FRAME_SIZE)

    if len(frame_data) != FRAME_SIZE:
        print("Неверный размер данных, ожидаем:", FRAME_SIZE)
        #time.sleep(0.03)
        continue

    frame = np.frombuffer(frame_data, dtype=np.uint8).reshape((FRAME_HEIGHT, FRAME_WIDTH, CHANNELS))
    #frame_copy = frame.copy()

    frame_count += 1
    print("Получен кадр №", frame_count)

    cv2.imshow("frame", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    time.sleep(0.03)

cv2.destroyAllWindows()
