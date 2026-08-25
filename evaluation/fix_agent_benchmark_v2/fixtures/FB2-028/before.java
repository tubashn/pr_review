package com.example.val;

public class RangeValidator {
    public boolean isOutOfRange(int val, int min, int max) {
        if (val < min && val > max) {
            return true;
        }
        return false;
    }
}
