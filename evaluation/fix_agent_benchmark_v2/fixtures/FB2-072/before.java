package com.example.geo;

public class CoordinateShift {
    private double x;
    private double y;
    public void shift(double dx, double dy) {
        this.x -= dx;
        this.y -= dy;
    }
    public double getX() { return x; }
    public double getY() { return y; }
}
