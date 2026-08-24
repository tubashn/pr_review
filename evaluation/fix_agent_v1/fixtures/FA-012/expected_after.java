package com.example.inventory;

public class StockAvailabilityService {
    public boolean isAvailable(int availableCount, int requestedCount) {
        return availableCount >= requestedCount;
    }
}
