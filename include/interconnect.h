#ifndef INTERCONNECT_H
#define INTERCONNECT_H

#include <string>
#include "logger.h"

// Performs the handshake over the serial port. Returns a valid file descriptor on success.
int interconnect_handshake(quill::Logger *logger);

// Reads from the serial port until a newline is encountered and returns the line.
std::string interconnect_bus(int fd);

// Sends a command ("SEND\n") to the Teensy, waits for a valid JSON message (from '{' to '}'),
// then sends an ACK ("ACK\n") and returns the JSON string.
std::string request_json(int fd);

#endif // INTERCONNECT_H
