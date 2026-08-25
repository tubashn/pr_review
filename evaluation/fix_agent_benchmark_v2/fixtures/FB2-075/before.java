package com.example.io;

import java.io.FileInputStream;
import java.io.IOException;

public class BinaryFileReader {
    public int readFirstByte(String path) throws IOException {
        FileInputStream fis = new FileInputStream(path);
        return fis.read();
    }
}
