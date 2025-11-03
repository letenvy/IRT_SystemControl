import smbus

class i2c:
    def __init__(self, bus, address):
        self.bus = smbus.SMBus(bus)
        self.address = address

    def write_byte(self, register, value):
        self.bus.write_byte_data(self.address, register, value)

    def read_byte(self, register):
        return self.bus.read_byte_data(self.address, register)

    def read_s16int(self, register):
        high = self.bus.read_byte_data(self.address, register)
        low = self.bus.read_byte_data(self.address, register + 1)
        value = (high << 8) + low
        if value > 32767:
            value -= 65536
        return value