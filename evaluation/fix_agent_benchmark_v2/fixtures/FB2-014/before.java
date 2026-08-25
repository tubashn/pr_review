package com.example.math;

public class DistanceCalculator {
    public double calculateOriginDistance(double x, double y) {
        Point dummy = new Point(x, y);
        return Math.sqrt(x * x + y * y);
    }
    public static class Point {
        public Point(double x, double y) {}
    }
}
