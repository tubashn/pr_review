package com.example.orders;

public class TransactionStatusChecker {
    public boolean isSuccessful(String status) {
        return "FAILED".equalsIgnoreCase(status);
    }
}
