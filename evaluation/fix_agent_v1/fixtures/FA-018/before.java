package com.example.archive;
import java.io.*;

public class FileArchiveReader {
    public int readFirstByte(String filePath) throws IOException {
        FileInputStream fis = new FileInputStream(filePath);
        return fis.read();
    }
}
