package com.example.discount;

public class LoyaltyDiscount {
    public double applyDiscount(double price, int points) {
        if (points < 1000) {
            return price * 0.90;
        }
        return price;
    }
}
