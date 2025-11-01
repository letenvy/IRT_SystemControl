#import asyncio
import serial
import time
import re

#async
def read_sensor_data(port='/dev/ttyACM0', baudrate=115200, reconnect_interval=5, max_no_data_time=5):
    ser = serial.Serial()
    ser.baudrate = 115200
    ser.port = port
    ser.open()
    ser.timeout = 1

    while True:
        try:
            print("Подключение к UWB датчику установлено")
            #sendLog("Подключение к UWB датчику установлено")
            last_valid_data_time = time.time()
            
            while True:
                if ser.in_waiting:
                    new_str = ser.readline().decode('ascii').strip()
                    if len(new_str) > 10:
                        log = str(new_str)
                        #print(log)
                        parser = re.search(r"[SOLVE].*?X:\s*([\d\.\-]+)\s*Y:\s*([\d\.\-]+)\s*Z:\s*([\d\.\-]+).*?anum:\s*(\d+)", log)
                        
                        if parser:
                            x, y, z, anum = parser.groups()
                            print(f'X:{x} Y:{y} Z:{z} anum:{anum}')
                            last_valid_data_time = time.time()
                            #print("last_valid_data_time ", last_valid_data_time)
                            
                        # else:
                            # print("Net валидных данных, переподключение датчика...")
                            # ser.close()
                            # ser.open()
                            # break
                    else:
                        print("Получены неверные данные")
                        ser.close()
                        ser.open()
                        break
                        
                if time.time() - last_valid_data_time > max_no_data_time:
                    print("Долгое отсутствие валидных данных, переподключение датчика...")
                    ser.close()
                    ser.open()
                    break
                time.sleep(0.01)
                
        except (serial.SerialException, OSError) as e:
            print(f"Ошибка соединения с датчиком: {e}")

if __name__ == "__main__":
    read_sensor_data(port='/dev/ttyACM0', baudrate=115200, reconnect_interval=5, max_no_data_time=5)
