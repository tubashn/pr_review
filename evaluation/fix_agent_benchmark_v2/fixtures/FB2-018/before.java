package com.example.search;

public class LinearScanner {
    public boolean containsTarget(int[] array, int target) {
        boolean flag = false;
        for (int v : array) {
            if (v == target) {
                flag = true;
                return true;
            }
        }
        return flag;
    }
}
