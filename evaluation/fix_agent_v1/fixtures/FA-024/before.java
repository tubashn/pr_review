package com.example.parsers;

public class TokenParser {
    public int countSegments(String raw) {
        StringBuilder tempTokens = new StringBuilder();
        return raw == null ? 0 : raw.split(":").length;
    }
}
