#!/usr/bin/env python
# vim: set fileencoding=UTF-8 :

# HMC5888L Magnetometer (Digital Compass) wrapper class
# Based on https://bitbucket.org/thinkbowl/i2clibraries/src/14683feb0f96,
# but uses smbus rather than quick2wire and sets some different init
# params.

import smbus
import math
import time
import sys
import json
import os
from robot import DifferentialDriveRobot

class HMC5883L:
    __scales = {
        0.88: [0, 0.73],
        1.30: [1, 0.92],
        1.90: [2, 1.22],
        2.50: [3, 1.52],
        4.00: [4, 2.27],
        4.70: [5, 2.56],
        5.60: [6, 3.03],
        8.10: [7, 4.35],
    }

    def __init__(self, port=1, address=0x1E, gauss=1.3, declination=(0, 0), calib_file="prikladniki/mag_calib_test.json", controlRobot=None):

        self.MaxRad = -10.0
        self.MinRad = 10.0

        self.bus = smbus.SMBus(port)
        self.address = address
        self._cal_bias_x = 0.0
        self._cal_bias_y = 0.0
        self._cal_bias_z = 0.0
        self._cal_scale_x = 1.0
        self._cal_scale_y = 1.0
        self._cal_scale_z = 1.0
        self._calib_file = calib_file
        self._load_calibration(self._calib_file)  # Попытка загрузить калибровку при старте

        
        self.__driveRobot = controlRobot
        print(f"Robot init = {self.__driveRobot}")

        (degrees, minutes) = declination
        self.__declDegrees = degrees
        self.__declMinutes = minutes
        self.__declination = (degrees + minutes / 60) * math.pi / 180

        (reg, self.__scale) = self.__scales[gauss]
        self.bus.write_byte_data(self.address, 0x00, 0x70)  # 8 Average, 15 Hz, normal measurement
        self.bus.write_byte_data(self.address, 0x01, reg << 5)  # Scale
        self.bus.write_byte_data(self.address, 0x02, 0x00)  # Continuous measurement

    def declination(self):
        return (self.__declDegrees, self.__declMinutes)

    def calibrate(self, ):
        mx_values = []
        my_values = []
        mz_values = []
        #self.__driveRobot.set_speed(-30, 30) #жоска крутится
        duration = time.time() + 30 #время записи значений для калибровки
        while time.time() < duration:
            x, y, z = self.read_data()
            print(f"read data: X={x}, Y={y}")
            mx_values.append(x)
            my_values.append(y)
            mz_values.append(z)
            time.sleep(0.05)

        """Сохраняет массив кала в TXT-файл."""
        try:
            with open("govniche.txt", 'w', encoding='utf-8') as f:
                for val1, val2, val3 in zip(mx_values, my_values, mz_values):
                    f.write(f"{val1},{val2},{val3}\n")
            print("массив кала сохранен в файл: govniche.txt")
        except Exception as e:
            print(f"[Ошибка] Не удалось сохранить кал")

        # === Min-Max калибровка (только X и Y) === жоские формулы
        min_x, max_x = min(mx_values), max(mx_values)
        min_y, max_y = min(my_values), max(my_values)
        min_z, max_z = min(mz_values), max(mz_values)

        bias_x = (max_x + min_x) / 2.0 #смещение
        bias_y = (max_y + min_y) / 2.0
        bias_z = (max_z + min_z) / 2.0

        range_x = max_x - min_x
        range_y = max_y - min_y
        range_z = max_z - min_z

        if range_x == 0 or range_y == 0 or range_z == 0:
            raise ValueError("[Калибровка] Диапазон измерений нулевой — Лохи, проверьте подключение магнитометра!")

        # Средний радиус (по полуразмахам)
        avg_radius = (range_x + range_y + range_z) / 6.0

        scale_x = avg_radius / (range_x / 2.0)
        scale_y = avg_radius / (range_y / 2.0)
        scale_z = avg_radius / (range_z / 2.0)

        calibrate = False
        self.set_calibration(bias_x, bias_y, bias_z, scale_x, scale_y, scale_z)
        self.save_calibration(self._calib_file)
        self.__driveRobot.stop()
    
    @classmethod
    def getCalibration(cls): return  cls._cal_bias_x, cls._cal_bias_y, cls._cal_scale_x, cls._cal_scale_y
    
    def set_calibration(self, bias_x, bias_y, bias_z, scale_x=1.0, scale_y=1.0, scale_z=1.0):
        self._cal_bias_x = bias_x
        self._cal_bias_y = bias_y
        self._cal_bias_z = bias_z
        self._cal_scale_x = scale_x
        self._cal_scale_y = scale_y
        self._cal_scale_z = scale_z

        print(f"[Калибровка] Применена: bias=({bias_x:.2f}, {bias_y:.2f}, {bias_z:.2f}), scale=({scale_x:.4f}, {scale_y:.4f}, {scale_z:.4f})")


    def save_calibration(self, filename=None):
        """Сохраняет калибровку в JSON-файл."""
        if filename is None:
            filename = self._calib_file

        calib_data = {
            "bias_x": self._cal_bias_x,
            "bias_y": self._cal_bias_y,
            "bias_z": self._cal_bias_z,
            "scale_x": self._cal_scale_x,
            "scale_y": self._cal_scale_y,
            "scale_z": self._cal_scale_z
        }

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(calib_data, f, indent=4)
            print(f"[Калибровка] Сохранена в файл: {filename}")
        except Exception as e:
            print(f"[Ошибка] Не удалось сохранить калибровку: {e}")


    def _load_calibration(self, filename=None):
        """Загружает калибровку из JSON-файла, если он существует."""
        if filename is None:
            filename = self._calib_file

        if not os.path.exists(filename):
            print(f"[Калибровка] Файл не найден: {filename}. Используется калибровка по умолчанию.")
            return

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.set_calibration(
                bias_x=data["bias_x"],
                bias_y=data["bias_y"],
                bias_z=data["bias_z"],
                scale_x=data["scale_x"],
                scale_y=data["scale_y"],
                scale_z=data["scale_z"]
            )
            print(f"[Калибровка] Загружена из файла: {filename}")
        except (KeyError, json.JSONDecodeError, IOError) as e:
            print(f"[Ошибка] Не удалось загрузить калибровку из {filename}: {e}")






    def twos_complement(self, val, len):
        # Convert twos compliment to integer
        if (val & (1 << len - 1)):
            val = val - (1 << len)
        return val

    def __convert(self, data, offset):
        val = self.twos_complement(data[offset] << 8 | data[offset + 1], 16)
        if val == -4096: return None
        return round(val * self.__scale, 4)

    def read_data(self):
        data = self.bus.read_i2c_block_data(self.address, 0x00)
        # print(data)
        
        # print map(hex, data)
        x = self.__convert(data, 3)
        y = self.__convert(data, 7)
        z = self.__convert(data, 5)
        # print(f'{x} {y} {z}')
        # print(y)
        # print(z)
        return (x, y, z)

    def heading(self):
        (x, y, z) = self.read_data()
        headingRad1 = math.atan2(y, x)
        # x = self._cal_scale_x * (x - self._cal_bias_x) #HARDCODE PEPEDGE
        # y = self._cal_scale_y * (y - self._cal_bias_y)
        z = self._cal_scale_z * (z - self._cal_bias_z)

        # print("self._cal_scale_x = ", self._cal_scale_x)
        # print("self._cal_scale_y = ", self._cal_scale_y)
        # print("self._cal_bias_x = ", self._cal_bias_x)
        # print("self._cal_bias_y = ", self._cal_bias_y)
        kx = 1.31684981684982
        ky = 0.806053811659193
        bx = -2517.76000000000
        by = 962.560000000000
        x = kx * (x - bx) #HARDCODE PEPEDGE
        y = ky * (y - by)

        headingRad = math.atan2(y, x)
        #print(headingRad * 180 / math.pi, headingRad1 * 180 / math.pi)
        headingRad += self.__declination
        #print('РАДИАНЫ', headingRad)

        # Correct for reversed heading
        if headingRad < 0:
            headingRad += 2 * math.pi

        # Check for wrap and compensate
        elif headingRad > 2 * math.pi:
            headingRad -= 2 * math.pi

        if headingRad > self.MaxRad:
            self.MaxRad = headingRad
        if headingRad < self.MinRad:
            self.MinRad = headingRad

        #print('Max', self.MaxRad, 'Min', self.MinRad) 
        # Convert to degrees from radians
        headingDeg = headingRad * 180 / math.pi
        return headingDeg #- 52.612433
        #print(headingDeg)
        time.sleep(0.05)

    def degrees(self, headingDeg):
        degrees = math.floor(headingDeg[0])
        minutes = round((headingDeg[1] - degrees) * 60)
        return (degrees, minutes)

    def __str__(self):
        (x, y, z) = self.read_data()
        return "Axis X: " + str(x) + "\n" + \
               "Axis Y: " + str(y) + "\n" + \
               "Axis Z: " + str(z) + "\n" + \
               "Declination: " + str(self.degrees(self.declination())) + "\n" + \
               "Heading: " + str(self.heading()) + "\n"


# if __name__ == "__main__":
#     # http://magnetic-declination.com/Great%20Britain%20(UK)/Harrogate#
#     compass = HMC5883L(gauss=4.7, declination=(7, 22))
#     while True:
#         print(compass.heading())
#         time.sleep(0.05)
