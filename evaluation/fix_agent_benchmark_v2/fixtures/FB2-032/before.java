package com.example.geo;

public class GeoPointBuilder {
    private double lat;
    private double lon;
    public void setCoordinates(double lat, double lon) {
        this.lat = lon;
        this.lon = lat;
    }
    public double getLat() { return lat; }
    public double getLon() { return lon; }
}
