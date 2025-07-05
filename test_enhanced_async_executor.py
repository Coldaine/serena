#!/usr/bin/env python3
"""
Test script for the enhanced AsyncToolExecutor with improved error handling and communication reliability.

This script demonstrates:
1. Health checking capabilities
2. Retry mechanisms
3. Stress testing
4. Communication failure detection
"""

import asyncio
import time
import logging
from pathlib import Path
import sys

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from serena.async_tool_executor import AsyncToolExecutor, UnifiedToolDispatcher, HealthChecker, StressTester

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('async_tool_test.log')
    ]
)

log = logging.getLogger(__name__)


async def failing_async_tool(failure_rate: float = 0.3):
    """An async tool that fails randomly to test retry logic."""
    import random
    
    # Simulate some work
    await asyncio.sleep(0.1)
    
    if random.random() < failure_rate:
        raise RuntimeError("Simulated async tool failure")
    
    return "async_success"


def failing_sync_tool(failure_rate: float = 0.3):
    """A sync tool that fails randomly to test retry logic."""
    import random
    
    # Simulate some work
    time.sleep(0.1)
    
    if random.random() < failure_rate:
        raise RuntimeError("Simulated sync tool failure")
    
    return "sync_success"


async def timeout_async_tool(delay: float = 10.0):
    """An async tool that times out to test timeout handling."""
    await asyncio.sleep(delay)
    return "timeout_success"


def timeout_sync_tool(delay: float = 10.0):
    """A sync tool that times out to test timeout handling."""
    time.sleep(delay)
    return "timeout_success"


def main():
    """Main test function."""
    log.info("Starting AsyncToolExecutor enhanced test suite")
    
    # Create and start the executor
    executor = AsyncToolExecutor()
    executor.start()
    
    try:
        # Create dispatcher with retry logic
        dispatcher = UnifiedToolDispatcher(executor, default_timeout=30.0, max_retries=2)
        
        # Test 1: Health Check
        log.info("=" * 50)
        log.info("Test 1: Health Check")
        log.info("=" * 50)
        
        health_checker = HealthChecker(executor)
        health_results = health_checker.comprehensive_health_check()
        
        log.info(f"Health check results: {health_results}")
        
        # Test 2: Basic tool execution
        log.info("=" * 50)
        log.info("Test 2: Basic Tool Execution")
        log.info("=" * 50)
        
        # Test async tool
        async def simple_async():
            await asyncio.sleep(0.1)
            return "basic_async_success"
        
        result = dispatcher.dispatch_tool(simple_async, {})
        log.info(f"Basic async tool result: {result}")
        
        # Test sync tool
        def simple_sync():
            time.sleep(0.1)
            return "basic_sync_success"
        
        result = dispatcher.dispatch_tool(simple_sync, {})
        log.info(f"Basic sync tool result: {result}")
        
        # Test 3: Retry logic with failing tools
        log.info("=" * 50)
        log.info("Test 3: Retry Logic")
        log.info("=" * 50)
        
        # Test retry with failing async tool
        try:
            result = dispatcher.dispatch_tool(failing_async_tool, {"failure_rate": 0.7})
            log.info(f"Failing async tool succeeded after retries: {result}")
        except Exception as e:
            log.error(f"Failing async tool failed permanently: {e}")
        
        # Test retry with failing sync tool
        try:
            result = dispatcher.dispatch_tool(failing_sync_tool, {"failure_rate": 0.7})
            log.info(f"Failing sync tool succeeded after retries: {result}")
        except Exception as e:
            log.error(f"Failing sync tool failed permanently: {e}")
        
        # Test 4: Timeout handling
        log.info("=" * 50)
        log.info("Test 4: Timeout Handling")
        log.info("=" * 50)
        
        # Test timeout with async tool
        try:
            result = dispatcher.dispatch_tool(timeout_async_tool, {"delay": 5.0}, timeout=2.0)
            log.info(f"Timeout async tool result: {result}")
        except Exception as e:
            log.error(f"Timeout async tool failed as expected: {e}")
        
        # Test timeout with sync tool
        try:
            result = dispatcher.dispatch_tool(timeout_sync_tool, {"delay": 5.0}, timeout=2.0)
            log.info(f"Timeout sync tool result: {result}")
        except Exception as e:
            log.error(f"Timeout sync tool failed as expected: {e}")
        
        # Test 5: Stress test
        log.info("=" * 50)
        log.info("Test 5: Stress Test")
        log.info("=" * 50)
        
        stress_tester = StressTester(dispatcher)
        stress_results = stress_tester.run_stress_test(num_tasks=20, concurrent_tasks=5)
        
        log.info(f"Stress test summary: {stress_results['summary']}")
        
        # Test 6: Communication failure simulation
        log.info("=" * 50)
        log.info("Test 6: Communication Failure Simulation")
        log.info("=" * 50)
        
        # Test ping functionality
        ping_success = executor.ping(timeout=5.0)
        log.info(f"Ping successful: {ping_success}")
        
        # Get executor stats
        stats = executor.get_stats()
        log.info(f"Executor stats: {stats}")
        
    except Exception as e:
        log.error(f"Test suite failed: {e}")
        raise
    finally:
        # Clean up
        executor.stop()
        log.info("AsyncToolExecutor test suite completed")


if __name__ == "__main__":
    main()
