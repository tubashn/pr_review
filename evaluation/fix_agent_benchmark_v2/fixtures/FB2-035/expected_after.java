package com.example.val;

public class StringValidator {
    public boolean isValidNonEmpty(String str) {
        if (str == null) return false;
        if (str.length() == 0) return false;
        return true;
    }
}
