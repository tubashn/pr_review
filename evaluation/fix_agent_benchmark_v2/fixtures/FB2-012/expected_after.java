package com.example.text;

public class Sanitizer {
    public String sanitize(String input) {
        if (input == null) return "";
        return input.trim();
    }
}
