package com.example.file;

import java.io.File;

public class FileDownloadHandler {
    public File getDownload(String userFilename) {
        File target = new File("/var/data/" + userFilename);
        return target;
    }
}
