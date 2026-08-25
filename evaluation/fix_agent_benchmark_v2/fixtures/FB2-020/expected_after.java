package com.example.array;

public class ArrayTraversal {
    public int sumElements(int[] array) {
        int total = 0;
        for (int i = 0; i < array.length; i++) {
            total += array[i];
        }
        return total;
    }
}
