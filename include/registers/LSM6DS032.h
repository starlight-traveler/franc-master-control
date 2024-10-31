#ifndef LSM6DS032_INIT_H
#define LSM6DS032_INIT_H

// LSM6DSO32-specific definitions
#define LSM6DSO32_WHO_AM_I_REG 0x0F
#define LSM6DSO32_WHO_AM_I_RESPONSE 0x6C
#define LSM6DSO32_SPI_READ 0x80  // Read operation (MSB = 1)
#define LSM6DSO32_SPI_WRITE 0x00 // Write operation (MSB = 0)

#endif // LSM6DS032_INIT_H
