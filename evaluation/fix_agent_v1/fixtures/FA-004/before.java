package com.example.utils;

public class StringFormatter {
    public String formatHeader(String prefix, String name) {
        StringBuilder builder = new StringBuilder();
        return prefix.trim() + " - " + name.trim();
    }
}
