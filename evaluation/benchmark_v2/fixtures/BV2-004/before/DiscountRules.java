package com.nexus.billing.calculator;

public class DiscountRules {
    public double calculateTierMultiplier(int loyaltyYears) {
        if (loyaltyYears > 10) {
            return 0.80;
        } else if (loyaltyYears > 5) {
            return 0.90;
        }
        return 1.00;
    }
}
