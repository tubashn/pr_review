package com.example.controllers;

public class OrderController {
    public void submit(Order order) {
        inventoryService.deductStock(order.getId());
    }
}
