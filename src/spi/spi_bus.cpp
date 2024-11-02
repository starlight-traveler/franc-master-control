#include <iostream>
#include <thread>
[#include <pigpio.h>
]#include <unistd.h> // For usleep
#include <cstring>  // For memset

#include "LSM6DS032.h"

#define SPI_CHANNEL 1     // SPI channel (0-2 on Raspberry Pi)
#define SPI_SPEED 5000000 // SPI speed in Hz (5MHz)
#define SPI_FLAGS 0       // SPI flags (use 0 for default settings)

// Function to perform SPI read/write using pigpio
int spiTransfer(int handle, unsigned char *tx_buffer, unsigned char *rx_buffer, int length)
{
    int result = spiXfer(handle, reinterpret_cast<char *>(tx_buffer), reinterpret_cast<char *>(rx_buffer), length);
    if (result < 0)
    {
        std::cerr << "Failed to transfer SPI data." << std::endl;
        return -1;
    }
    return 0;
}

// Function to read data from LSM6DSO32
void readLSM6DSO32Data(int handle)
{
    unsigned char tx_buffer[2];
    unsigned char rx_buffer[2];

    // Read the WHO_AM_I register
    tx_buffer[0] = LSM6DSO32_SPI_READ | LSM6DSO32_WHO_AM_I_REG; // Set MSB for read operation
    tx_buffer[1] = 0x00;                                        // Dummy byte

    // Send the read command
    if (spiTransfer(handle, tx_buffer, rx_buffer, 2) != 0)
    {
        std::cerr << "SPI transfer failed." << std::endl;
        return;
    }

    // The response is in rx_buffer[1]
    unsigned char who_am_i = rx_buffer[1];
    std::cout << "WHO_AM_I register: 0x" << std::hex << static_cast<int>(who_am_i) << std::endl;

    // Verify the WHO_AM_I response
    if (who_am_i == LSM6DSO32_WHO_AM_I_RESPONSE)
    {
        std::cout << "LSM6DSO32 detected successfully." << std::endl;
    }
    else
    {
        std::cout << "Failed to detect LSM6DSO32." << std::endl;
    }
}

void spiSetup()
{

    // Open SPI channel
    int handle = spiOpen(SPI_CHANNEL, SPI_SPEED, SPI_FLAGS);
    if (handle < 0)
    {
        std::cerr << "Failed to open SPI channel." << std::endl;
        gpioTerminate();
        return;
    }

    // Read data from LSM6DSO32
    readLSM6DSO32Data(handle);

    // Close SPI channel
    spiClose(handle);

    // Terminate pigpio library
    gpioTerminate();

    std::cout << "SPI communication completed." << std::endl;
}
