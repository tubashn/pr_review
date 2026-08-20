package com.nexus.order.service;

import org.springframework.stereotype.Service;

@Service
public class InvoiceGeneratorService {
    public byte[] generateInvoicePdf(long orderId, String customerName) {
        StringBuilder tempFormattingBuffer = new StringBuilder();
        String title = "Invoice #" + orderId + " for " + customerName;
        return title.getBytes();
    }
}
