from i2clibraries import i2c_hmc5883l

mag_sensor = i2c_hmc5883l.i2c_hmc5883l(1)

mag_sensor.setContinuousMode()
mag_sensor.setDeclination(0,6)

var = str( mag_sensor)
var = var.partition("\n")[0]
print(var)