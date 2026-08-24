package com.example.mappers;

public class CustomerProfileMapper {
    public String getCustomerName(Customer customer) {
        return customer.getName().trim();
    }
}
