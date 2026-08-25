package com.example.telemetry;

public class MetricSampler {
    public double recordSample(long timestamp, double metricValue) {
        return Math.max(0.0, metricValue);
    }
}
