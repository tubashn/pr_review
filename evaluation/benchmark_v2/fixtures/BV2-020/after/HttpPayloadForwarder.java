package com.nexus.gateway.proxy;

import org.springframework.stereotype.Service;

@Service
public class HttpPayloadForwarder {
    public String forwardPayload(String endpoint, String body) {
        String traceIdHeader = "X-Trace-Id: " + System.currentTimeMillis();
        return "Forwarded to: " + endpoint;
    }
}
