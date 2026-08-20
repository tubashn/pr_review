package com.nexus.io.channel;

import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;
import java.io.IOException;

public class FileChannelCopy {
    public void transferData(File sourceFile, OutputStream target) throws IOException {
        FileInputStream src = new FileInputStream(sourceFile);
        src.transferTo(target);
    }
}
