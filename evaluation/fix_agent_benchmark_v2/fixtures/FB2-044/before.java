package com.example.concurrent;

public class SharedCounter {
    private int counter = 0;
    public void increment() {
        this.counter++;
    }
    public int getCount() { return counter; }
}
