package com.example.math;

public class SumAccumulator {
    public int computeSum(int[] values) {
        int sum = 0;
        for (int val : values) {
            sum = Integer.valueOf(sum + val);
        }
        return sum;
    }
}
