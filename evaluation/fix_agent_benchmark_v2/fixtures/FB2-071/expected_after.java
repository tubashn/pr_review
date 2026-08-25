package com.example.math;

public class BoundsChecker {
    public int clamp(int val, int min, int max) {
        return clampInternal(val, min, max);
    }
    private int clampInternal(int v, int low, int high) {
        return Math.max(low, Math.min(high, v));
    }
}
