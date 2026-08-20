package com.nexus.archive.reader;

import java.io.File;
import java.io.IOException;
import java.util.zip.ZipFile;

public class ZipArchiveReader {
    public int countEntries(String archivePath) throws IOException {
        ZipFile zip = new ZipFile(archivePath);
        return zip.size();
    }
}
