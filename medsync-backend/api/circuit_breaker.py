"""
Circuit Breaker Pattern for external integrations.

Provides resilience for:
- NHIS API (mock)
- Push notification gateway
- AI inference services

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, requests fail fast
- HALF_OPEN: Testing if service recovered

Configuration:
- 5 consecutive failures → open circuit
- 60 second wait before retry (half-open)
- 3 successful requests in half-open → close circuit
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional
from threading import Lock

from django.core.cache import cache

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    half_open_success_threshold: int = 3
    

class CircuitBreaker:
    """
    Circuit breaker for a single service.
    
    Usage:
        nhis_breaker = CircuitBreaker("nhis_api")
        
        @nhis_breaker.protect
        def call_nhis_api():
            ...
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._lock = Lock()
        self._cache_prefix = f"circuit_breaker:{name}"
    
    def _cache_key(self, key: str) -> str:
        return f"{self._cache_prefix}:{key}"
    
    @property
    def state(self) -> CircuitState:
        state_str = cache.get(self._cache_key("state"), CircuitState.CLOSED.value)
        return CircuitState(state_str)
    
    @state.setter
    def state(self, value: CircuitState):
        cache.set(self._cache_key("state"), value.value, timeout=3600)
    
    @property
    def failure_count(self) -> int:
        return cache.get(self._cache_key("failures"), 0)
    
    @failure_count.setter
    def failure_count(self, value: int):
        cache.set(self._cache_key("failures"), value, timeout=3600)
    
    @property
    def last_failure_time(self) -> Optional[float]:
        return cache.get(self._cache_key("last_failure"))
    
    @last_failure_time.setter
    def last_failure_time(self, value: float):
        cache.set(self._cache_key("last_failure"), value, timeout=3600)
    
    @property
    def half_open_successes(self) -> int:
        return cache.get(self._cache_key("half_open_successes"), 0)
    
    @half_open_successes.setter
    def half_open_successes(self, value: int):
        cache.set(self._cache_key("half_open_successes"), value, timeout=3600)
    
    def is_available(self) -> bool:
        """Check if circuit allows requests."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self.last_failure_time:
                    elapsed = time.time() - self.last_failure_time
                    if elapsed >= self.config.recovery_timeout:
                        logger.info(f"Circuit {self.name}: transitioning to half-open")
                        self.state = CircuitState.HALF_OPEN
                        self.half_open_successes = 0
                        return True
                return False
            
            # HALF_OPEN - allow request
            return True
    
    def record_success(self):
        """Record a successful call."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_successes += 1
                if self.half_open_successes >= self.config.half_open_success_threshold:
                    logger.info(f"Circuit {self.name}: closing after recovery")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
            else:
                # Reset failure count on success in closed state
                self.failure_count = 0
    
    def record_failure(self, error: Exception):
        """Record a failed call."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            logger.warning(f"Circuit {self.name}: failure #{self.failure_count} - {error}")
            
            if self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open immediately opens
                logger.warning(f"Circuit {self.name}: opening (failed during half-open)")
                self.state = CircuitState.OPEN
            elif self.failure_count >= self.config.failure_threshold:
                logger.warning(f"Circuit {self.name}: opening (threshold reached)")
                self.state = CircuitState.OPEN
    
    def protect(self, func: Callable) -> Callable:
        """Decorator to protect a function with circuit breaker."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.is_available():
                raise CircuitOpenError(
                    f"Circuit breaker {self.name} is open. "
                    f"Service unavailable, please try again later."
                )
            
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure(e)
                raise
        
        return wrapper
    
    def get_status(self) -> dict:
        """Get circuit breaker status for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure": self.last_failure_time,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
            }
        }


class CircuitOpenError(Exception):
    """Raised when circuit is open and request should fail fast."""
    pass


# Pre-configured circuit breakers for common integrations
nhis_circuit = CircuitBreaker("nhis_api")
push_notification_circuit = CircuitBreaker("push_notifications")
ai_inference_circuit = CircuitBreaker("ai_inference", CircuitBreakerConfig(
    failure_threshold=3,  # AI is expensive, fail faster
    recovery_timeout=120,  # Wait longer before retry
))


def get_all_circuit_statuses() -> list:
    """Get status of all circuit breakers for admin dashboard."""
    return [
        nhis_circuit.get_status(),
        push_notification_circuit.get_status(),
        ai_inference_circuit.get_status(),
    ]
