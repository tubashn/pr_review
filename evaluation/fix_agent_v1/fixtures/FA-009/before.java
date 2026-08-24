package com.example.pricing;

public class DiscountCalculator {
    public double applyVolumeDiscount(double subtotal, int itemCount) {
        if (itemCount < 10) {
            return subtotal * 0.90;
        }
        return subtotal;
    }
}
