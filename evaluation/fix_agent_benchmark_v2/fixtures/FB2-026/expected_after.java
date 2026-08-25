package com.example.str;

public class PrefixExtractor {
    public String extractPrefix(String text, int maxLength) {
        if (text == null) return "";
        if (text.length() > maxLength) {
            return text.substring(0, maxLength);
        }
        return text;
    }
}
