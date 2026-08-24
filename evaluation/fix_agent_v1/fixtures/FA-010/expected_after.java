package com.example.io;

public class ArrayBufferReader {
    public byte readByte(byte[] buffer, int index) {
        if (index < 0 || index >= buffer.length) {
            return -1;
        }
        return buffer[index];
    }
}
