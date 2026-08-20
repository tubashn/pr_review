package com.nexus.collections.defensive;

import java.util.List;

public class ImmutableListHelper {
    public <T> List<T> copyElementsSafely(List<T> inputList) {
        return inputList == null ? List.of() : List.copyOf(inputList);
    }
}
