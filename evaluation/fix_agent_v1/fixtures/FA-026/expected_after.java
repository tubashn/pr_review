package com.example.queues;

public class QueueProcessor {
    public String getLastItem(String[] items) {
        if (items == null || items.length == 0) return null;
        return items[items.length - 1];
    }
}
