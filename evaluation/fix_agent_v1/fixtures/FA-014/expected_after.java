package com.example.orders;

public class TransactionStatusChecker {
    public boolean isSuccessful(String status) {
        return "SUCCESS".equalsIgnoreCase(status);
    }
}
