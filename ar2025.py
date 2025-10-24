# test_motors.py
import RPi.GPIO as GPIO
import time
from robot import DifferentialDriveRobot
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)


#  ------------------------------------------Constants----------------------------------
LEFT_ENABLE = 13
LEFT_PIN1 = 19
LEFT_PIN2 = 16

RIGHT_ENABLE = 20
RIGHT_PIN1 = 21
RIGHT_PIN2 = 26

if __name__ == "__main__":
    thisDifferentionalDriveRobot=DifferentialDriveRobot(LEFT_ENABLE,
                                                        LEFT_PIN1,
                                                        LEFT_PIN2,
                                                        RIGHT_ENABLE,
                                                        RIGHT_PIN1,
                                                        RIGHT_PIN2)
    try:
        
        thisDifferentionalDriveRobot.turn_right(10,100,duration=5)
        thisDifferentionalDriveRobot.turn_left(100,10,duration=5)
        """"
        print("1")
        thisDifferentionalDriveRobot.forward(speed=50,duration=5)
        print("2")
        thisDifferentionalDriveRobot.backward(speed=50,duration=5)
        print("3")
        thisDifferentionalDriveRobot.turn_left_tank(speed=50,duration=5)
        print("4")
        thisDifferentionalDriveRobot.turn_right_tank(speed=50,duration=5)
        """

    finally:
        thisDifferentionalDriveRobot.cleanup()