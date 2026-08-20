package com.nexus.billing.calculator;

public class DiscountRules {
    public double calculateTierMultiplier(int loyaltyYears) {
        if (loyaltyYears > 5) {
            return 0.90;
        } else if (loyaltyYears > 5) {
            return 0.85;
        }
        return 1.00;
    }
}
