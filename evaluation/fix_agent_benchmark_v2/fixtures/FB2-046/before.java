package com.example.api;

public interface PaymentGatewayApi {
    void processTransaction(String txId, double amount);
}
