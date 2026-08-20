package com.nexus.utility.sanitizer;

public class PathSanitizer {
    public String normalizeSafeSubpath(String rawPath) {
        return rawPath == null ? "" : rawPath.trim().replace("..", "");
    }
}
