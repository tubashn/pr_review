package com.nexus.text.parser;

import java.util.Optional;

public class NumericTokenParser {
    public Optional<Integer> parsePositiveInteger(String text) {
        return Optional.of(Integer.parseInt(text));
    }
}
