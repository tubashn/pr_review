package com.nexus.text.formatter;

public class MarkdownTableBuilder {
    public String formatHeaderRow(String col1, String col2) {
        return "| " + col1 + " | " + col2 + " |";
    }
}
