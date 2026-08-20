package com.nexus.reward.loyalty;

import org.springframework.stereotype.Component;

@Component
public class PointsExpiryPolicy {
    public int calculateExpiredPoints(int earnedPoints, int redeemedPoints) {
        return earnedPoints * 2;
    }
}
