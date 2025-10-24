import cv2
import numpy as np
import os
import mmap
import tempfile
import time

# Параметры кадра
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
CHANNELS = 3
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT * CHANNELS

# Получаем путь к временной директории для текущей ОС
temp_dir = tempfile.gettempdir()
SHM_FILENAMES = [os.path.join(temp_dir, "shm_frame0"), os.path.join(temp_dir, "shm_frame1")]

def get_mmap_buffer(filename, size):
    """
    Если файла нет, создаёт его и заполняет нулями, затем открывает для чтения/записи с помощью mmap.
    """
    if not os.path.exists(filename):
        with open(filename, "wb") as f:
            f.write(b'\x00' * size)
        print(f"Файл {filename} создан")
    fd = os.open(filename, os.O_RDWR)
    mm = mmap.mmap(fd, size)
    os.close(fd)
    return mm

# Получаем два буфера для двойного буфера
shm_buffers = [get_mmap_buffer(fname, FRAME_SIZE) for fname in SHM_FILENAMES]

# Захват видео с камеры
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Не удалось открыть камеру")
    exit(1)

current_buffer = 0
frame_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        print("Ошибка: не удалось получить кадр с камеры")
        break

    # Изменяем размер кадра на заданный (если необходимо)
    frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
    frame_count += 1
    # print("Кадр №", frame_count)

    # Выбираем неактивный буфер для записи нового кадра (двойное переключение)
    next_buffer = 1 - current_buffer
    buf = shm_buffers[next_buffer]
    buf.seek(0)
    # Записываем кадр в виде последовательности байтов
    buf.write(frame.tobytes())
    # Опционально: сбрасываем изменения на диск
    #buf.flush()

    # Обновляем индекс текущего буфера
    current_buffer = next_buffer

    # # Опциональное отображение полученного кадра
    # cv2.imshow("Камера", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    #
    time.sleep(0.03)  # Примерно 30 FPS

cap.release()
cv2.destroyAllWindows()

# По завершении можно удалить файлы, если они больше не нужны:
for fname in SHM_FILENAMES:
    try:
        os.remove(fname)
        print(f"Файл {fname} удалён")
    except Exception as e:
        print(f"Ошибка удаления файла {fname}: {e}")
