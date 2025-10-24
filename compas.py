import smbus
import time
import math
import json
import os
 
# Настройки
I2C_BUS = 1
DEVICE_ADDR = 0x1E
CALIB_FILE = "calibration.json"
DECLINATION = 8.22  # Магнитное склонение для Москвы (подставьте свое)

bus = smbus.SMBus(I2C_BUS)
def init_magnetometer():
    """Инициализация магнитометра"""
    bus.write_byte_data(DEVICE_ADDR, 0x0B, 0x1D)  # Конфигурация
    bus.write_byte_data(DEVICE_ADDR, 0x09, 0x0D)   # Сброс
    time.sleep(0.1)

def read_raw_data():
    """Чтение сырых данных магнитометра"""
    data = bus.read_i2c_block_data(DEVICE_ADDR, 0x00, 6)
    x = data[0] | (data[1] << 8)
    y = data[2] | (data[3] << 8)
    z = data[4] | (data[5] << 8)
    x = x if x < 32768 else x - 65536
    y = y if y < 32768 else y - 65536
    z = z if z < 32768 else z - 65536
    return x, y, z

def calibrate(duration=30):
    """Калибровка магнитометра"""
    print("Начинаем калибровку...")
    print("Поворачивайте модуль во всех направлениях в течение", duration, "секунд")
    
    # Инициализация значений
    min_x = max_x = min_y = max_y = min_z = max_z = None
    
    start_time = time.time()
    while time.time() - start_time < duration:
        x, y, z = read_raw_data()
        
        if min_x is None:
            min_x = max_x = x
            min_y = max_y = y
            min_z = max_z = z
        else:
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)
            min_z = min(min_z, z)
            max_z = max(max_z, z)
        
        print(f"X: {x:>6} ({min_x:>6}/{max_x:>6}) | Y: {y:>6} ({min_y:>6}/{max_y:>6}) | Z: {z:>6} ({min_z:>6}/{max_z:>6})")
        time.sleep(0.1)
    
    # Рассчет смещений и масштабирующих коэффициентов
    offset_x = (min_x + max_x) / 2
    offset_y = (min_y + max_y) / 2
    offset_z = (min_z + max_z) / 2
    
    avg_delta_x = (max_x - min_x) / 2
    avg_delta_y = (max_y - min_y) / 2
    avg_delta_z = (max_z - min_z) / 2
    avg_delta = (avg_delta_x + avg_delta_y + avg_delta_z) / 3
    
    scale_x = avg_delta / avg_delta_x
    scale_y = avg_delta / avg_delta_y
    scale_z = avg_delta / avg_delta_z
    
    calibration_data = {
        'offset_x': offset_x,
        'offset_y': offset_y,
        'offset_z': offset_z,
        'scale_x': scale_x,
        'scale_y': scale_y,
        'scale_z': scale_z
    }
    
    # Сохранение в файл
    with open(CALIB_FILE, 'w') as f:
        json.dump(calibration_data, f)
    
    print("\nКалибровка завершена!")
    print("Данные сохранены в", CALIB_FILE)
    print("Смещения (offset):", calibration_data)
    print("Масштабные коэффициенты (scale):", scale_x, scale_y, scale_z)

def load_calibration(ws_path = None):
    """Загрузка калибровочных данных"""
    if ws_path is None:
        print(os.path)
        if not os.path.exists(CALIB_FILE):
            raise FileNotFoundError(f"Файл калибровки {CALIB_FILE} не найден!")
        
        with open(CALIB_FILE, 'r') as f:
            data = json.load(f)
    else:
        with open(ws_path+'/config/calibration.json', 'r') as f:
            data = json.load(f)
    return data

def calculate_heading(x, y, declination=0):
    """Вычисление угла курса с учетом магнитного склонения"""
    heading_rad = math.atan2(y, x)
    heading_deg = math.degrees(heading_rad)
    heading_deg += declination  # Коррекция склонения
    
    # Нормализация в диапазон 0-360°
    if heading_deg < 0:
        heading_deg += 360
    elif heading_deg >= 360:
        heading_deg -= 360
        
    return heading_deg

def get_cardinal_direction(heading):
    """Определение стороны света"""
    directions = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
    index = round(heading / 45) % 8
    return directions[index]

if __name__ == "__main__":
    # Инициализация
    init_magnetometer()
    calib = load_calibration()
    
    print("Используются калибровочные параметры:")
    print(calib)
    print("\nНажмите Ctrl+C для остановки")
    print("----------------------------")
    
    try:
        while True:
            # Чтение сырых данных
            x, y, z = read_raw_data()
            
            # Применение калибровки
            x_cal = (x - calib['offset_x']) * calib['scale_x']
            y_cal = (y - calib['offset_y']) * calib['scale_y']
            z_cal = (z - calib['offset_z']) * calib['scale_z']
            
            # Вычисление курса
            heading = calculate_heading(x_cal, y_cal, DECLINATION)
            direction = get_cardinal_direction(heading)
            
            # Вывод результатов
            print(f"Курс: {heading:6.1f}° ({direction}) | X: {x_cal:7.1f} | Y: {y_cal:7.1f} | Z: {z_cal:7.1f}")
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        print("\nПрограмма остановлена")
