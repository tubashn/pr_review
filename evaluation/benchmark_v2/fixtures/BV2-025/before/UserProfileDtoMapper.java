package com.nexus.customer.mapper;

import org.springframework.stereotype.Component;

@Component
public class UserProfileDtoMapper {
    public UserEntity mapToEntity(UserProfileDto dto) {
        UserEntity entity = new UserEntity();
        entity.setUsername(dto.getUsername());
        entity.setEmailAddress(dto.getEmailAddress());
        entity.setPhoneNumber(dto.getPhoneNumber());
        return entity;
    }
}
