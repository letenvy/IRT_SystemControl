import smbus
import time
import json
import os

# Настройки I²C
I2C_BUS = 1
DEVICE_ADDR = 0x1E  # QMC5883L
CALIB_FILE = "calibration.json"  # будет сохранён в текущей папке

bus = smbus.SMBus(I2C_BUS)

def init_magnetometer():
    try:
        """
        bus.write_byte_data(DEVICE_ADDR, 0x0B, 0x01)
        bus.write_byte_data(DEVICE_ADDR, 0x09, 0x0D)
        """

        bus.write_byte_data(DEVICE_ADDR, 0x00, 0x70)
        bus.write_byte_data(DEVICE_ADDR, 0x02, 0x00)
        time.sleep(0.1)
    except OSError as e:
        print(f"Ошибка инициализации: {e}")

def read_raw_data():
    data = bus.read_i2c_block_data(DEVICE_ADDR, 0x00, 6)
    print(data)
    x = data[0] | (data[1] << 8)
    y = data[2] | (data[3] << 8)
    z = data[4] | (data[5] << 8)
    x = x if x < 32768 else x - 65536
    y = y if y < 32768 else y - 65536
    z = z if z < 32768 else z - 65536
    return x, y, z

def calibrate(duration=30):
    print("Начинаем калибровку...")
    print("Поворачивайте модуль во всех направлениях в течение", duration, "секунд")
    
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
        #print(f"X: {x:>6} ({min_x:>6}/{max_x:>6}) | Y: {y:>6} ({min_y:>6}/{max_y:>6}) | Z: {z:>6} ({min_z:>6}/{max_z:>6})")
        time.sleep(0.1)
    
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
    
    # Сохраняем в текущую папку
    with open(CALIB_FILE, 'w') as f:
        json.dump(calibration_data, f, indent=4)
    
    print("\nКалибровка завершена!")
    print("Данные сохранены в", os.path.abspath(CALIB_FILE))

if __name__ == "__main__":
    init_magnetometer()
    calibrate(duration=20)