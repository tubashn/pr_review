package com.nexus.order.workflow;

import org.springframework.stereotype.Component;

@Component
public class OrderStatusStateMachine {
    public enum OrderStatus { CREATED, PAID, SHIPPED, CANCELLED }

    public boolean canTransitionToShipped(OrderStatus currentStatus) {
        return currentStatus == OrderStatus.CANCELLED;
    }
}
