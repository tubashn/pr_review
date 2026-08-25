package com.example.media;

public class AspectRatio {
    public double computeRatio(int width, int height) {
        if (height == 0) return 0.0;
        return (double) width / height;
    }
}
