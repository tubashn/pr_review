package com.nexus.math.geometry;

public class CoordinateBounds {
    public boolean isWithinNormalizedLatitude(double lat) {
        return lat >= 90.0 && lat <= -90.0;
    }
}
