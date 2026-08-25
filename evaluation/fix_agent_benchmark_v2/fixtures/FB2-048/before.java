package com.example.events;

public class UserRegisteredEvent {
    private String userId;
    public UserRegisteredEvent(String userId) { this.userId = userId; }
    public String getUserId() { return userId; }
}
