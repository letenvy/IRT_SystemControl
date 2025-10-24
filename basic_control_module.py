import RPi.GPIO as GPIO
import cv2
import numpy as np
import atexit
import i2c_itg3205 as i2c_itg
import i2c_adxl345 as i2c_adxl
import websocket
import json
from threading import Thread, Event
import time
import math
import pupil_apriltags as apriltag
import os
import mmap
import tempfile


cars = []
yourCarPosition = []

#Vars and consts for Forward movement
LEFT_RUL = 0
RIGHT_RUL = 72
MAX_CAR_SPEED = 40
LEFT_DASHED_LINE_GOOD_POS = 6
RIGHT_SOLID_LINE_GOOD_POS = 53
FRAME_MID_POS = 32

angle = 36
stop_car = None
fwd_event = Event()
stop_event = Event()
one_line_flag = None
pos = 32
rul_bias = 110
frame = None

node_des = [0, 0]
node_pos = [[6.65, 0.40],
            [2.10, 0.40],
            [0.40, 0.40],
            [0.40, 2.80],
            [0.40, 4.00],
            [0.40, 7.25],
            [2.90, 7.25],
            [4.90, 7.25],
            [6.65, 7,25],
            [6.65, 5.00],
            [2.65, 2.20],
            [3.45, 1.60],
            [4.35, 3.00],
            [2.90, 4.00],
            [4.90, 5.00]]


# -------------------- ИНИЦИАЛИЗАЦИЯ GPIO --------------------
# Сбрасываем предыдущие настройки (если есть)
GPIO.cleanup()
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Motor drive interface definition
ENA = LEFT_MOTOR_ENABLE = 13  # L298 Enable A
ENB = RIGHT_MOTOR_ENABLE = 12  # L298 Enable B
IN1 = LEFT_MOTOR_PIN1 = 19  # Motor interface 1
IN2 = LEFT_MOTOR_PIN2 = 16  # Motor interface 2
IN3 = RIGHT_MOTOR_PIN1 = 21  # Motor interface 3
IN4 = RIGHT_MOTOR_PIN2 = 26  # Motor interface 4

# Motor initialized to LOW
GPIO.setup(ENA, GPIO.OUT)
GPIO.setup(IN1, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(IN2, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(ENB, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(IN4, GPIO.OUT, initial=GPIO.LOW)

pwmA = GPIO.PWM(ENA, 100)
pwmB = GPIO.PWM(ENB, 100)
pwmA.start(0)
pwmB.start(0)

# -------------------- ИНИЦИАЛИЗАЦИЯ ИНЕРЦИАЛКИ -----------------------------
itg3205 = i2c_itg.i2c_itg3205(1)
adxl345 = i2c_adxl.i2c_adxl345(1)

# -------------------- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ЭНКОДЕРА --------------------

#--------------------- Настройки камеры для тегов -------------------------------
# constants for camera
fx, fy, cx, cy = 612.96693998, 550.05464024, 310.29614756, 241.95032088
camera_matrix = np.array([[fx, 0, cx],
                          [0, fy, cy],
                          [0, 0, 1]], dtype=np.float64)
dist_coeffs = np.array([-1.27217630e-01, 8.94699033e-01, -2.11854682e-03, -3.03787945e-03, -2.75853136e+00])

tag_size = 0.1
trajectories = {}
detector = apriltag.Detector()

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


def localization(r,tag_size,camera_matrix, dist_coeffs):
    pts = np.array([r.corners], dtype=np.float32).reshape((4, 2))

    object_points = np.array([
        [-tag_size / 2, -tag_size / 2, 0],
        [tag_size / 2, -tag_size / 2, 0],
        [tag_size / 2, tag_size / 2, 0],
        [-tag_size / 2, tag_size / 2, 0]
    ], dtype=np.float32)

    success, rvec, tvec = cv2.solvePnP(object_points, pts, camera_matrix, dist_coeffs)

    return success,tvec


class KalmanFilter1D:

    def __init__(self, dt=1 / 20, process_noise=0.5, measurement_noise=10.0):
        self.X = np.array([[0.0],
                           [0.0]])  # [x, v]
        self.P = np.eye(2) * 1000.0

        self.dt = dt
        self.A = np.array([[1.0, self.dt],
                           [0.0, 1.0]])
        self.H = np.array([[1.0, 0.0]])
        self.Q = np.eye(2) * process_noise
        self.R = np.array([[measurement_noise]])
        self.I = np.eye(2)

    def predict(self):
        self.X = self.A @ self.X
        self.P = self.A @ self.P @ self.A.T + self.Q

    def update(self, z):
        z = np.array([[z]])
        y = z - self.H @ self.X
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.X = self.X + K @ y
        self.P = (self.I - K @ self.H) @ self.P

    def get_position(self):
        return self.X[0, 0]


def filter_contours_by_area(mask, min_area=200, max_area=50000):
    mask_filtered = mask.copy()
    contours, _ = cv2.findContours(mask_filtered, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            cv2.drawContours(mask_filtered, [cnt], -1, (0, 0, 0), -1)
    return mask_filtered


def estimate_lane_target(line_positions, roi_width, prev_joystick_x, min_gap=1000):
    if not line_positions:
        return None, (None, None)

    sorted_positions = sorted(line_positions)
    clusters = []
    current_cluster = [sorted_positions[0]]
    for pos in sorted_positions[1:]:
        if pos - current_cluster[-1] < min_gap:
            current_cluster.append(pos)
        else:
            clusters.append(np.mean(current_cluster))
            current_cluster = [pos]
    clusters.append(np.mean(current_cluster))

    if len(clusters) >= 2:
        left_boundary = min(clusters)
        right_boundary = max(clusters)
        target = (left_boundary + right_boundary) / 2.0
        return target, (left_boundary, right_boundary)
    else:
        detected = clusters[0]
        if prev_joystick_x is None:
            prev_joystick_x = roi_width / 2.0
        if roi_width / 2.0 < detected:
            missing = detected - roi_width / 2.0 - 300
        else:
            missing = detected + roi_width / 2.0 + 300
        target = (detected + missing) / 2.0
        left_boundary = min(detected, missing)
        right_boundary = max(detected, missing)
        return target, (left_boundary, right_boundary)



# -------------------- ФУНКЦИЯ ДЛЯ СЕРВОПРИВОДА --------------------
def set_angle(angle):
    """
    Устанавливает угол сервопривода (0°...180°).
    Для MG996R часто: 0° соответствует ~2.5% duty cycle, 180° — ~12.5%.
    Задержка уменьшена до 0.1 с для быстрой реакции.
    """
    duty = (angle / 18.0) + 2.5
    servo_pwm.ChangeDutyCycle(duty)
    time.sleep(0.15)
    servo_pwm.ChangeDutyCycle(0)


def set_motor_speeds(left_speed, right_speed):
    """Устанавливает скорости для левого и правого моторов"""
    # Левый мотор
    if left_speed > 0:
        GPIO.output(LEFT_MOTOR_PIN1, GPIO.HIGH)
        GPIO.output(LEFT_MOTOR_PIN2, GPIO.LOW)
    else:
        GPIO.output(LEFT_MOTOR_PIN1, GPIO.LOW)
        GPIO.output(LEFT_MOTOR_PIN2, GPIO.HIGH)
    pwmA.ChangeDutyCycle(abs(left_speed))

    # Правый мотор
    if right_speed > 0:
        GPIO.output(RIGHT_MOTOR_PIN1, GPIO.HIGH)
        GPIO.output(RIGHT_MOTOR_PIN2, GPIO.LOW)
    else:
        GPIO.output(RIGHT_MOTOR_PIN1, GPIO.LOW)
        GPIO.output(RIGHT_MOTOR_PIN2, GPIO.HIGH)
    pwmB.ChangeDutyCycle(abs(right_speed))

def MotorForward(speed):
    print('Движение вперед')
    set_motor_speeds(speed, speed)

def MotorBackward(speed):
    print('Движение назад')
    set_motor_speeds(-speed, -speed)

def MotorTurnRight():
    print('Поворот направо (танковое управление)')
    set_motor_speeds(-70, 70)  # Левый вперед, правый назад

def MotorTurnLeft():
    print('Поворот налево (танковое управление)')
    set_motor_speeds(70, -70)  # Левый назад, правый вперед

def MotorStop():
    print('Остановка')
    pwmA.ChangeDutyCycle(0)
    pwmB.ChangeDutyCycle(0)
    # Сбрасываем пины в LOW состояние
    GPIO.output(LEFT_MOTOR_PIN1, GPIO.LOW)
    GPIO.output(LEFT_MOTOR_PIN2, GPIO.LOW)
    GPIO.output(RIGHT_MOTOR_PIN1, GPIO.LOW)
    GPIO.output(RIGHT_MOTOR_PIN2, GPIO.LOW)

# -------------------- ФУНКЦИЯ ПОВОРОТА РОБОТА --------------------
def turn_by_angle(target_angle_deg, base_speed=80):
    """
    Поворачивает робота на заданный угол (в градусах) с использованием гироскопа.

    Положительный угол (например, 90°) – поворот влево, отрицательный – вправо.

    Во время поворота:
      - Сервопривод устанавливается в соответствующее положение:
          • 0° для поворота влево,
          • 72° для поворота вправо.
      - Интегрируются показания угловой скорости гироскопа.
      - Скорость мотора корректируется пропорционально оставшейся ошибке.
      - Счётчик энкодера используется для контроля переезда (защита от избыточного поворота).
    """
    # Переводим целевой угол в радианы
    target_angle = math.radians(target_angle_deg)
    dt = 0.02  # интервал цикла 20 мс
    tolerance = math.radians(1)  # допускаемая погрешность 1°

    # Пропорциональный коэффициент для регуляции скорости
    proportional_gain = base_speed / abs(target_angle) if target_angle != 0 else 0
    min_speed = 30  # минимальная скорость для преодоления инерции
    max_speed = base_speed

    # Получаем начальное значение угловой скорости по оси Z
    try:
        _, _, start_z = itg3205.getDegPerSecAxes()
    except OSError:
        print("Ошибка чтения гироскопа при инициализации.")
        start_z = 0

    current_angle = 0.0  # интегрированный угол поворота (в радианах)
    print(f"Начало поворота на {target_angle_deg}°")
    start_time = time.time()
    # Установка угла сервопривода: для поворота вправо (отрицательный угол) – 72°, для поворота влево – 0°
    if target_angle_deg < 0:
        MotorTurnRight()
    else:
        MotorTurnLeft()

    while abs(target_angle - current_angle) > tolerance:
        loop_start = time.time()
        try:
            # Считываем текущую угловую скорость по оси Z (в градусах/сек)
            _, _, z = itg3205.getDegPerSecAxes()
        except OSError:
            print("Ошибка чтения гироскопа, пропуск итерации.")
            continue

        # Интегрируем угловую скорость: преобразуем (z - start_z) из град/сек в радианы
        current_angle += -math.radians(z - start_z) * dt
        error = target_angle - current_angle
        computed_speed = proportional_gain * abs(error)
        speed = max(min_speed, min(max_speed, computed_speed))

        # Отладочный вывод
        print(f"Цель: {math.degrees(target_angle):.2f}°, Текущий: {math.degrees(current_angle):.2f}°, "
              f"Ошибка: {math.degrees(error):.2f}°, Скорость: {speed:.1f}%, Энкодер: {encoder_count}")

        elapsed = time.time() - loop_start
        if dt - elapsed > 0:
            time.sleep(dt - elapsed)
    

    MotorStop()
    total_time = time.time() - start_time
    print(f"Поворот завершён. Итоговый угол: {math.degrees(current_angle):.2f}°, "
          f"Время: {total_time:.2f} сек, Импульсов энкодера: {encoder_count}")


def GetPosition():
    x = yourCarPosition[0]
    y = yourCarPosition[1]
    return x, y


def GetDistance():

    StartTime = time.time()
    StopTime = time.time()
    GPIO.output(TRIG, False)
    time.sleep(0.1)
    GPIO.output(TRIG, True)
    time.sleep(0.00001)
    GPIO.output(TRIG, False)

    while GPIO.input(ECHO) == 0:
        StartTime = time.time()

    while GPIO.input(ECHO) == 1:
        StopTime = time.time()

    pulseDuration = (StopTime - StartTime)
    distance = pulseDuration * 17000
    if pulseDuration >= 0.01746:
        return 0, 'Time out'
    elif distance > 300 or distance == 0:
        return distance, 'Out of range'

    return distance, 'Ok'


def cam_check():
    cam_test = 20
    for i in range(cam_test):
        try:
            cam = cv2.VideoCapture(i)
            test, frame = cam.read()
            if test:
                return i
            cam.release()
        except:
            pass
    return None


def camera_routine():
    global stop_car
    global angle
    global pos
    global frame
    show = False
    # Получаем список "буферов" – маппинг файлов
    shm_buffers = [get_mmap_buffer(fname, FRAME_SIZE) for fname in SHM_FILENAMES]

    # Пример простого цикла, который читает данные из первого буфера
    latest_index = 0
    frame_count = 0
    while True:
        fwd_event.wait()

        # First parameters 0.5 10.0
        kf = KalmanFilter1D(dt=1 / 20, process_noise=1, measurement_noise=30.0)

        max_step = 150
        prev_joystick_x = None

        adaptive_offset = 70
        MotorForward(30)

        buf = shm_buffers[latest_index]
        buf.seek(0)  # перемещаем указатель в начало
        frame_data = buf.read(FRAME_SIZE)

        if len(frame_data) != FRAME_SIZE:
            print("Неверный размер данных, ожидаем:", FRAME_SIZE)
            # time.sleep(0.03)
            continue

        frame = np.frombuffer(frame_data, dtype=np.uint8).reshape((FRAME_HEIGHT, FRAME_WIDTH, CHANNELS))
        if frame is None:
            print('I dont see avaliable cameras around...')
            time.sleep(1)
        else:
            while True:
                buf = shm_buffers[latest_index]
                buf.seek(0)  # перемещаем указатель в начало
                frame_data = buf.read(FRAME_SIZE)

                if len(frame_data) != FRAME_SIZE:
                    print("Неверный размер данных, ожидаем:", FRAME_SIZE)
                    # time.sleep(0.03)
                    continue

                frame = np.frombuffer(frame_data, dtype=np.uint8).reshape((FRAME_HEIGHT, FRAME_WIDTH, CHANNELS))

                height, width = frame.shape[:2]
                roi_vertical_start = int(height * 0.4)
                roi = frame[roi_vertical_start:height, :].copy()
                roi_height = roi.shape[0]
                roi_width = width

                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                apt_detect = detector.detect(gray)
                if apt_detect is not None:
                    for r in apt_detect:
                        success, tvec = localization(r, tag_size, camera_matrix, dist_coeffs)
                        if success:
                            relative_x = tvec[0]
                            relative_y = -tvec[1]
                            print(f'found {r.tag_id} at x={relative_x} y={relative_y} z={tvec[2]}')
                            sl = (relative_y ** 2 + tvec[2] ** 2) ** 0.5 - 0.18
                            print(f'square = {sl}')
                            if sl < 0.45:
                                stop_car = True
                h, s, v = cv2.split(hsv)
                avg_v = np.mean(v)
                v_thresh = int(avg_v + adaptive_offset)
                lower_white = np.array([0, 0, v_thresh])
                upper_white = np.array([180, 60, 255])
                white_mask = cv2.inRange(hsv, lower_white, upper_white)

                kernel = np.ones((5, 5), np.uint8)
                mask_open = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN, kernel)
                mask_close = cv2.morphologyEx(mask_open, cv2.MORPH_CLOSE, kernel)
                mask_filtered = filter_contours_by_area(mask_close, min_area=200, max_area=50000)

                edges = cv2.Canny(mask_filtered, 50, 150)

                lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=50, maxLineGap=50)
                line_positions = []
                if lines is not None:
                    for line_ in lines:
                        x1, y1, x2, y2 = line_[0]
                        dx = x2 - x1
                        dy = y2 - y1
                        if dx == 0:
                            continue
                        slope = dy / dx
                        if abs(slope) < 0.1:
                            continue
                        cv2.line(roi, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        b = y1 - slope * x1
                        x_intersect = int((roi_height - 1 - b) / slope)
                        if x_intersect > 840:
                            x_intersect = 840
                        elif x_intersect < -200:
                            x_intersect = 200
                        line_positions.append(x_intersect)
                        cv2.circle(roi, (x_intersect, roi_height - 1), 5, (255, 0, 0), -1)

                if not line_positions:
                    adaptive_offset = max(0, adaptive_offset - 2)
                else:
                    adaptive_offset = 70

                lane_target, (left_boundary, right_boundary) = estimate_lane_target(
                    line_positions, roi_width, prev_joystick_x, min_gap=300)
                # filtration
                kf.predict()
                if lane_target is not None:
                    kf.update(lane_target)

                predicted_x = kf.get_position()

                if prev_joystick_x is None:
                    prev_joystick_x = predicted_x
                delta = predicted_x - prev_joystick_x
                if abs(delta) > max_step:
                    predicted_x = prev_joystick_x + np.sign(delta) * max_step
                prev_joystick_x = predicted_x

                joystick_x = int(np.clip(predicted_x, 0, width - 1))
                joystick_y = roi_vertical_start + roi_height - 1
                # cv2.circle(frame, (joystick_x, joystick_y), 10, (0, 0, 255), -1)
                rul_x = joystick_x / 320 * 36
                # cv2.putText(frame, f"Joystick: {joystick_x}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                # cv2.putText(frame, f"Rul: {rul_x}", (10, 130), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

                angle = rul_x
                # if left_boundary is not None and right_boundary is not None:
                    # cv2.line(frame, (int(left_boundary), roi_vertical_start), (int(left_boundary), height),(255, 255, 0), 2)
                    # cv2.line(frame, (int(right_boundary), roi_vertical_start), (int(right_boundary), height),(255, 255, 0), 2)

                if show:
                    cv2.imshow('Frame', frame)
                    #cv2.imshow('White Mask', white_mask)
                    #cv2.imshow('Mask After Morph', mask_close)
                    #cv2.imshow('Mask Filtered', mask_filtered)
                    #cv2.imshow('Edges', edges)
                    cv2.imshow('ROI', roi)

                if stop_car:
                    MotorStop()
                    print("stopline found")
                    stop_car = True
                    fwd_event.clear()
                    stop_event.set()
                    break


def turn_routine():
    while True:
        fwd_event.wait()
        while not stop_car:
            angle_local = angle
            print(angle_local)
            set_angle(angle_local)
        set_angle(36)


def fwd_thrds_start():
    global stop_car
    stop_car = True
    turn_thread = Thread(target=turn_routine, daemon=True)
    camera_thread = Thread(target=camera_routine, daemon=True)
    
    ws2 = websocket.WebSocketApp("ws://localhost:8765", on_message=on_message, on_close=on_close, on_open=on_open)
    new_p2 = Thread(target=ws2.run_forever)
    new_p2.start()
    time.sleep(2)
    
    camera_thread.start()
    turn_thread.start()
    
    
def go_forward():
    global stop_car
    stop_car = False
    fwd_event.set()
    stop_event.clear()
    stop_event.wait()
    if fwd_event.is_set():
        fwd_event.clear()
    MotorStop()


class Graph:
    def __init__(self):
        self.GraphDict = {
            1: [2, 10],
            2: [1, 3, 12],
            3: [2, 4],
            4: [3, 5, 11],
            5: [4, 6, 14],
            6: [5, 7],
            7: [6, 8, 14],
            8: [7, 9, 15],
            9: [8, 10],
            10: [1, 9, 15],
            11: [12],
            12: [2, 13],
            13: [11, 15],
            14: [5, 7, 15],
            15: [8, 10, 13, 14]
        }
        self.WeightDict = {
            1: [5.5, 5.0],
            2: [5.5, 1.3, 2.5],
            3: [1.3, 3.0],
            4: [3.0, 1.0, 2.5],
            5: [1.0, 3.5, 2.4],
            6: [3.5, 2.4],
            7: [2.4, 2.4, 3.5],
            8: [2.4, 2.0, 2.5],
            9: [2.0, 2.5],
            10: [5.0, 2.5, 2.0],
            11: [0.5],
            12: [2.5, 1.0],
            13: [2.0, 2.5],
            14: [2.4, 3.5, 2.3],
            15: [2.5, 2.0, 2.5, 2.3]
        }
        self.RotDict = {
            1: [0, 270],
            2: [180, 0, 290],
            3: [180, 270],
            4: [90, 270, 180],
            5: [90, 270, 180],
            6: [90, 180],
            7: [0, 180, 90],
            8: [0, 180, 90],
            9: [0, 90],
            10: [90, 270, 0],
            11: [90],
            12: [270, 180],
            13: [270, 180],
            14: [0, 270, 180],
            15: [270, 180, 90, 0]
        }
        self.base_info = []


class Rover:
    def __init__(self, cur_pos, cur_rot, graph, r_bi = 110):
        global rul_bias
        if cur_pos > 0 and cur_pos < 16:
            self.pos = cur_pos
        else:
            print("Cannot initialize here. Assuming starting position at point 1")
            self.star_pos = 1
        self.star_rot = cur_rot % 360
        self.prev_pos = None
        self.cur_rot = self.star_rot
        self.graph = graph
        self.distance = 0
        self.route = [self.pos]
        self.recorder = []
        rul_bias = r_bi
        graph.base_info.append(f"start {cur_pos} {cur_rot}")
        fwd_thrds_start()

    def mov_to_point(self, point):
        if point > 0 and point < 16:
            if point in self.graph.GraphDict[self.pos]:
                dest_index = self.graph.GraphDict[self.pos].index(point)
                if point == 11:
                    self.cur_rot = 90
                elif point == 12:
                    self.cur_rot = 180
                elif self.pos == 13 and self.cur_rot == 180:
                    self.cur_rot = 270
                elif self.pos == 13 and self.cur_rot == 90:
                    self.cur_rot = 0
                elif self.pos == 15 and self.prev_pos == 13:
                    self.cur_rot == 270
                else:
                    self.cur_rot = self.graph.RotDict[self.pos][dest_index]
                self.route.append(point)
                self.prev_pos = self.pos
                self.pos = point
                self.distance += self.graph.WeightDict[self.prev_pos][dest_index]
                print(f"Rover has moved from node {self.prev_pos} to node {self.pos}")
                print(f"Current rot is {self.cur_rot} degrees")
                print(f"Distance went - {self.graph.WeightDict[self.prev_pos][dest_index]} m, Total - {self.distance} m")
                self.recorder.append(f"mov {self.pos} {self.cur_rot} succ")
            else:
                print("Node not connected to the current position!")
                self.recorder.append(f"mov {self.pos} fail")
        else:
            print("There is no such node!")
            self.recorder.append(f"mov {self.prev_pos} {self.pos} erro")

    def rotate(self, degrees):
        self.cur_rot = (self.cur_rot + degrees) % 360
        print(f"New Course - {self.cur_rot} degrees")
        self.recorder.append(f"rot {degrees} {self.cur_rot}")

    def go_to_forward_node(self):
        global node_des
        course = self.cur_rot
        print(f"Going forward! Course {course}")
        if course in self.graph.RotDict[self.pos]:
            point = self.graph.GraphDict[self.pos][self.graph.RotDict[self.pos].index(course)]
            node_des = node_pos[int(point) - 1]
            set_angle(36)
            if self.pos == 15:
                if self.cur_rot == 270 or self.cur_rot == 90:
                    turn_by_angle(40)
                    turn_by_angle(-40)
            if self.pos == 13 and self.cur_rot == 180:
                turn_by_angle(-60)
                MotorForward(40)
                time.sleep(1)
                turn_by_angle(30)
            time.sleep(2)
            go_forward()
            if self.pos == 11 and self.prev_pos == 13:
                go_forward()
            print("thats all she wrote")
            time.sleep(5)
            self.mov_to_point(point)
        else:
            print("Going off course!")
            self.recorder.append(f"mov {self.prev_pos} {self.pos} fail")
            
    def rot_custon(self, x):
        self.rotate(x)
        turn_by_angle(x)
        time.sleep(1)


def on_message(ws, mess):
    jmes = json.loads(mess)
    if jmes["action"] == "SendAllCoords":
        cars.append({"carName":jmes["data"]["carName"], "position": jmes["data"]["position"] })
    elif jmes["action"] == "SendPos":
        global yourCarPosition
        yourCarPosition = jmes["position"]
    elif jmes["action"] == "Cam":
        global frame
        frame = jmes["frame"]


def on_close(ws):
    ws.close()


def on_open(ws):
    print("Connection open")


def close():
    print("end", flush=True)
    MotorStop()
    cv2.destroyAllWindows()


atexit.register(close)
