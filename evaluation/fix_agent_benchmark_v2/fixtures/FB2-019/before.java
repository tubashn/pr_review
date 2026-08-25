package com.example.parser;

public class CharCounter {
    public int countDigits(String text) {
        int iterationIndex = 0;
        int count = 0;
        for (char c : text.toCharArray()) {
            iterationIndex++;
            if (Character.isDigit(c)) {
                count++;
            }
        }
        return count;
    }
}
