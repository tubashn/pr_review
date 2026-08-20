package com.nexus.cache.lru;

import java.util.Map;
import java.util.HashMap;
import java.util.function.Function;

public class BoundedLruCache<K, V> {
    private final Map<K, V> map = new HashMap<>();

    public V getOrCompute(K key, Function<K, V> mappingFunction) {
        return map.computeIfAbsent(key, mappingFunction);
    }
}
