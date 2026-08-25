package com.example.batch;

import java.util.List;

public class BatchTaskRunner {
    public int countValid(List<String> items) {
        int count = 0;
        if (items != null && items.size() > 0) {
            for (String item : items) {
                if (item != null) count++;
            }
        }
        return count;
    }
}
