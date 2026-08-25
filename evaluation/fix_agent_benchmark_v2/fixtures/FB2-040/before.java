package com.example.db;

public class UserSearchDao {
    public String buildSearchQuery(String email) {
        String sql = "SELECT * FROM users WHERE email = '" + email + "'";
        return sql;
    }
}
