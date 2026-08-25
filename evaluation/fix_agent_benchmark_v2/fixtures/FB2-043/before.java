package com.example.service;

public class OrderProcessor {
    public String getZip(Order order) {
        return order.getCustomer().getAddress().getZipCode();
    }
    public interface Order { Customer getCustomer(); }
    public interface Customer { Address getAddress(); }
    public interface Address { String getZipCode(); }
}
