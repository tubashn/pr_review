package com.nexus.inventory.service;

import org.springframework.stereotype.Service;

@Service
public class StockService {
    public boolean isEligibleForRestock(int availableQuantity, int minimumThreshold) {
        return availableQuantity < minimumThreshold;
    }
}
