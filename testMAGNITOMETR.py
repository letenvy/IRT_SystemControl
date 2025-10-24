from i2c_hmc5883l import *
MAGA = i2c_hmc5883l(1)
MAGA.setContinuousMode()
MAGA.setDeclination(9, 54)

print(MAGA.getHeading())