#!/usr/bin/env python3
import math
import cmath

class Ringbuffer:
    """
    A simple ring buffer for complex floats.

    This buffer holds up to `capacity` items and allows
    insertion (write) and reading (read) with wrap-around.
    """

    def __init__(self, capacity):
        self.capacity = capacity
        self.buffer = [0+0j] * capacity
        self.read_index = 0
        self.write_index = 0
        self.size = 0

    def insert(self, item: complex):
        """
        Insert one item into the ring buffer, overwriting
        the oldest data if the buffer is full.
        """
        self.buffer[self.write_index] = item
        self.write_index = (self.write_index + 1) % self.capacity
        if self.size < self.capacity:
            self.size += 1
        else:
            # If the buffer is full, move the read_index
            # so it also advances by one.
            self.read_index = (self.read_index + 1) % self.capacity

    def remove(self, count: int):
        """
        Remove `count` items by advancing the read pointer.
        """
        if count > self.size:
            count = self.size
        self.read_index = (self.read_index + count) % self.capacity
        self.size -= count

    def __getitem__(self, index: int) -> complex:
        """
        Allows direct read access to the buffer items:
            item = ringbuffer[i]
        """
        if index >= self.size:
            raise IndexError("Ringbuffer index out of range")
        idx = (self.read_index + index) % self.capacity
        return self.buffer[idx]

    def readAvailable(self) -> int:
        """
        Returns how many items can be read from the buffer.
        """
        return self.size

    def writeAvailable(self) -> int:
        """
        Returns how many items can be written to the buffer before it's full.
        """
        return self.capacity - self.size
