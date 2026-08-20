package com.nexus.text.parser;

import java.util.Optional;

public class NumericTokenParser {
    public Optional<Integer> parsePositiveInteger(String text) {
        if (text == null || text.isBlank()) {
            return Optional.empty();
        }
        try {
            int val = Integer.parseInt(text.trim());
            return val > 0 ? Optional.of(val) : Optional.empty();
        } catch (NumberFormatException e) {
            return Optional.empty();
        }
    }
}
