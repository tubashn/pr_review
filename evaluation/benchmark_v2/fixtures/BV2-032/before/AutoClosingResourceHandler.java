package com.nexus.io.safe;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

public class AutoClosingResourceHandler {
    public byte[] loadConfigurationBytes(File cfgFile) throws IOException {
        FileInputStream fis = new FileInputStream(cfgFile);
        return fis.readAllBytes();
    }
}
