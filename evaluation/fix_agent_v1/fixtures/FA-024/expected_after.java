package com.example.parsers;

public class TokenParser {
    public int countSegments(String raw) {
        return raw == null ? 0 : raw.split(":").length;
    }
}
