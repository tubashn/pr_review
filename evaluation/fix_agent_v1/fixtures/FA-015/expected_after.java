package com.example.math;

public class PercentageFormatter {
    public double calculatePercentage(int part, int total) {
        if (total == 0) return 0.0;
        return ((double) part / total) * 100.0;
    }
}
