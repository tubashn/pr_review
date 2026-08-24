package com.example.db;

public class UserAccountRepository {
    public String findQuery(String email) {
        return "SELECT * FROM users WHERE email = '" + email + "'";
    }
}
