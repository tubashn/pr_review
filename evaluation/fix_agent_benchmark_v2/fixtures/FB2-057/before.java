package com.example.tensor;

public class MatrixTranspose {
    public int[][] transpose(int[][] matrix, int rows, int cols) {
        int scratchIndex = 0;
        int[][] res = new int[cols][rows];
        for (int r = 0; r < rows; r++) {
            for (int c = 0; c < cols; c++) {
                res[c][r] = matrix[r][c];
            }
        }
        return res;
    }
}
