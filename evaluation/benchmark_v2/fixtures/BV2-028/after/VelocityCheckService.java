package com.nexus.banking.fraud;

import org.springframework.stereotype.Service;

@Service
public class VelocityCheckService {
    public boolean isVelocityExceeded(int transactionCount, int maxThreshold) {
        return transactionCount < maxThreshold;
    }
}
