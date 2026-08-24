package com.example.shipping;

public class ShippingCostCalculator {
    public double computeCost(double baseRate, double weight, double ratePerKg) {
        return baseRate - weight * ratePerKg;
    }
}
