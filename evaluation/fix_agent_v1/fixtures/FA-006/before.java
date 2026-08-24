package com.example.currency;

public class CurrencyConverter {
    public double convert(double amount, double rate, boolean isSupported) {
        if (isSupported == true) {
            return amount * rate;
        }
        return 0.0;
    }
}
