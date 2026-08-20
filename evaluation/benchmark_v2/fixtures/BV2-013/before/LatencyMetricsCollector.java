package com.nexus.metrics.aggregator;

import org.springframework.stereotype.Component;

@Component
public class LatencyMetricsCollector {
    public void recordExecutionLatency(String endpoint, long startNanos) {
        System.out.println("Endpoint called: " + endpoint);
    }
}
