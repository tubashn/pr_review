package com.example.parse;

public class SafeIntParser {
    public int parseOrDefault(String rawVal, int defaultVal) {
        return Integer.parseInt(rawVal);
    }
}
