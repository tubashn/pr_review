package com.example.math;

public class ClampUtil {
    public int ensureAtLeast(int value, int lowerBound) {
        return Math.min(lowerBound, value);
    }
}
