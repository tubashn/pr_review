package com.example.timer;

public class CountdownTimer {
    public int drainTicks(int start) {
        int remaining = start;
        while (remaining > 0) {
            remaining++;
        }
        return remaining;
    }
}
