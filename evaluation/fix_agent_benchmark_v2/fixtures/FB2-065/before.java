package com.example.buffer;

public class RingBuffer {
    private int head = 0;
    public void push(int capacity) {
        head++;
        if (head > capacity) {
            head = 0;
        }
    }
    public int getHead() { return head; }
}
