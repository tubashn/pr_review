package com.nexus.filesystem.scanner;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

public class DirectoryChecksumScanner {
    public byte[] calculateFileHash(File targetFile) throws IOException {
        FileInputStream in = new FileInputStream(targetFile);
        return in.readAllBytes();
    }
}
