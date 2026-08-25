package com.example.util;

import java.util.List;

public class ListChecker {
    public boolean hasElements(List<String> items) {
        boolean isEmpty = items.size() == 0;
        return isEmpty;
    }
}
