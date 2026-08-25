package com.example.search;

public class LinearScanner {
    public boolean containsTarget(int[] array, int target) {
        for (int v : array) {
            if (v == target) {
                return true;
            }
        }
        return false;
    }
}
