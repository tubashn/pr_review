package com.example.math;

public class LerpCalculator {
    public double lerp(double start, double end, double t) {
        return start + end - start * t;
    }
}
