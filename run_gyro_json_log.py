from src.gyroscope.GyroscopeClass import GyroscopeClass

if __name__ == "__main__":
    gyro = GyroscopeClass(port=1, addr=0x68)
    gyro.log_to_json("gyro_log.json")