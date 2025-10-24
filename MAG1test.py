import smbus
import time

bus = smbus.SMBus(1)
ADDR = 0x1E

# Инициализация HMC5883L
bus.write_byte_data(ADDR, 0x00, 0x70)  # 8x averaging, 15Hz
bus.write_byte_data(ADDR, 0x01, 0x20)  # Gain = ±1.3 Ga
bus.write_byte_data(ADDR, 0x02, 0x00)  # Continuous mode

time.sleep(0.1)

def read_hmc5883l():
    data = bus.read_i2c_block_data(ADDR, 0x03, 6)
    x = (data[0] << 8) | data[1]
    z = (data[2] << 8) | data[3]  # да, Z между X и Y!
    y = (data[4] << 8) | data[5]
    
    x = x - 65536 if x > 32767 else x
    y = y - 65536 if y > 32767 else y
    z = z - 65536 if z > 32767 else z
    
    return x, y, z
# Использование
print("Поворачивайте модуль...")
for _ in range(30):
    x, y, z = read_hmc5883l()
    print(f"X: {x:>6}, Y: {y:>6}, Z: {z:>6}")
    time.sleep(0.5)