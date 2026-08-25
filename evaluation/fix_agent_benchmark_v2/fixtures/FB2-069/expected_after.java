package com.example.stats;

public class AverageScore {
    public double computeAverage(int totalScore, int count) {
        if (count == 0) return 0.0;
        return (double) totalScore / count;
    }
}
