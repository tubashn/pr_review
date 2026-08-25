package com.example.render;

public class TableRenderer {
    public String render(String[][] data) {
        StringBuilder sb = new StringBuilder();
        // 25 lines of legacy table formatting
        for (int i = 0; i < data.length; i++) {
            for (int j = 0; j < data[i].length; j++) {
                sb.append("| ").append(data[i][j]).append(" ");
            }
            sb.append("|\n");
        }
        return sb.toString();
    }
}
