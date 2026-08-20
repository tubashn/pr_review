package com.nexus.reward.loyalty;

import org.springframework.stereotype.Component;

@Component
public class PointsExpiryPolicy {
    public int calculateExpiredPoints(int earnedPoints, int redeemedPoints) {
        int remaining = earnedPoints - redeemedPoints;
        return Math.max(0, remaining);
    }
}
