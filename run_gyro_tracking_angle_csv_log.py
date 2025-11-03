from src.gyroscope.GyroscopeClass import GyroscopeClass

if __name__ == "__main__":
    gyro = GyroscopeClass(port=1, addr=0x68)

    if not gyro.load_bias_from_file("gyro_bias.json"):
        print("Calibrate json not found, so new one creating...")
        gyro.calibrate_and_save("gyro_bias.json",samples=10000,delay=0.005)
        gyro.load_bias_from_file("gyro_bias.json")
    gyro.track_angles(filename="angles_log.csv",deadband=0.15)