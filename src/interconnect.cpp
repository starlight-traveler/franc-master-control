#include "interconnect.h"
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <sys/ioctl.h>
#include <iostream>

// Internal helper: configure the serial port (8N1, no flow control)
static int configureSerialPort(int fd, int baudRate)
{
    struct termios tty;
    memset(&tty, 0, sizeof(tty));
    if (tcgetattr(fd, &tty) != 0)
    {
        std::cerr << "Error from tcgetattr: " << strerror(errno) << std::endl;
        return -1;
    }

    speed_t speed = B115200;
    switch (baudRate)
    {
    case 115200:
        speed = B115200;
        break;
    case 9600:
        speed = B9600;
        break;
    default:
        speed = B115200;
        break;
    }

    cfsetospeed(&tty, speed);
    cfsetispeed(&tty, speed);

    tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8; // 8-bit chars
    tty.c_cflag &= ~PARENB;                     // no parity
    tty.c_cflag &= ~CSTOPB;                     // one stop bit
    tty.c_cflag &= ~CRTSCTS;                    // no hardware flow control
    tty.c_cflag |= (CLOCAL | CREAD);            // enable receiver

    tty.c_lflag = 0;
    tty.c_oflag = 0;
    tty.c_iflag = 0;

    tty.c_cc[VMIN] = 0;
    tty.c_cc[VTIME] = 0;

    if (tcsetattr(fd, TCSANOW, &tty) != 0)
    {
        std::cerr << "Error from tcsetattr: " << strerror(errno) << std::endl;
        return -1;
    }
    return 0;
}

int interconnect_handshake(quill::Logger *logger)
{
    const char *serialPort = "/dev/ttyACM0";
    int fd = open(serialPort, O_RDWR | O_NOCTTY | O_SYNC);
    if (fd < 0)
    {
        LOG_ERROR(logger, "Error opening serial port {}: {}", serialPort, strerror(errno));
        return -1;
    }

    if (configureSerialPort(fd, 115200) < 0)
    {
        LOG_ERROR(logger, "Error configuring serial port {}", serialPort);
        close(fd);
        return -1;
    }

    const char *handshakeMsg = "HELLO\n";
    if (write(fd, handshakeMsg, std::strlen(handshakeMsg)) < 0)
    {
        LOG_ERROR(logger, "Error writing handshake message: {}", strerror(errno));
        close(fd);
        return -1;
    }

    char buf[128];
    int attempts = 0;
    bool handshakeDone = false;
    while (attempts < 50 && !handshakeDone)
    {
        usleep(100000); // wait 100 ms
        int n = read(fd, buf, sizeof(buf) - 1);
        if (n > 0)
        {
            buf[n] = '\0';
            if (std::strstr(buf, "ACKHELLO") != nullptr)
            {
                handshakeDone = true;
            }
        }
        attempts++;
    }

    if (!handshakeDone)
    {
        LOG_ERROR(logger, "Handshake not completed on serial port {}", serialPort);
        close(fd);
        return -1;
    }

    LOG_INFO(logger, "Serial handshake successful on {}", serialPort);
    return fd;
}

std::string interconnect_bus(int fd)
{
    char buf[1024];
    std::string line;
    int pos = 0;
    while (true)
    {
        int n = read(fd, buf + pos, sizeof(buf) - pos - 1);
        if (n > 0)
        {
            pos += n;
            buf[pos] = '\0';
            char *newline = std::strchr(buf, '\n');
            if (newline != nullptr)
            {
                int lineLen = newline - buf;
                line = std::string(buf, lineLen);
                int remaining = pos - (lineLen + 1);
                std::memmove(buf, newline + 1, remaining);
                pos = remaining;
                buf[pos] = '\0';
                break;
            }
        }
        else
        {
            usleep(100000); // wait 100 ms if no data
            break;
        }
    }
    return line;
}

// ---------------------------------------------------------------------
// request_json()
// Sends a command "SEND\n" to the Teensy, waits until a valid JSON string
// (starting with '{' and ending with '}') is received, prints out what is
// received for debugging, sends "ACK\n", and returns the JSON string.
// ---------------------------------------------------------------------
std::string request_json(int fd)
{
    const char *cmd = "SEND\n";
    if (write(fd, cmd, std::strlen(cmd)) < 0)
    {
        std::cerr << "Error writing SEND command" << std::endl;
        return "";
    }

    std::string jsonMsg;
    const int maxAttempts = 50;
    int attempts = 0;
    while (attempts < maxAttempts)
    {
        jsonMsg = interconnect_bus(fd);

        // Trim leading and trailing whitespace
        while (!jsonMsg.empty() && (jsonMsg.front() == ' ' || jsonMsg.front() == '\r' || jsonMsg.front() == '\n'))
            jsonMsg.erase(0, 1);
        while (!jsonMsg.empty() && (jsonMsg.back() == ' ' || jsonMsg.back() == '\r' || jsonMsg.back() == '\n'))
            jsonMsg.pop_back();

        // std::cout << "DEBUG: Raw received: " << jsonMsg << std::endl;
        // Check if the message looks like JSON (starts with '{' and ends with '}')
        if (!jsonMsg.empty() && jsonMsg.front() == '{' && jsonMsg.back() == '}')
        {
            break;
        }
        attempts++;
    }

    // Send ACK to indicate receipt.
    const char *ackCmd = "ACK\n";
    write(fd, ackCmd, std::strlen(ackCmd));

    // std::cout << "DEBUG: Final JSON: " << jsonMsg << std::endl;
    return jsonMsg;
}