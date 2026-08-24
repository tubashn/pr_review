package com.example.payments;

public class PaymentValidator {
    public boolean validateTransaction(boolean isAuthorized, double amount) {
        if (amount <= 0) {
            return false;
        }
        if (isAuthorized) {
            return true;
        }
        return false;
    }
}
