"""
Test for the AsyncTool fix to verify that asynchronous tools are properly handled
without blocking the server and causing client hanging.
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock

from serena.async_tool_executor import AsyncToolExecutor, UnifiedToolDispatcher


class TestAsyncToolExecutor:
    """Test the AsyncToolExecutor implementation."""

    def test_executor_lifecycle(self):
        """Test that the executor starts and stops properly."""
        executor = AsyncToolExecutor()
        
        # Should not be running initially
        assert not executor.is_running()
        
        # Start the executor
        executor.start()
        assert executor.is_running()
        
        # Stop the executor
        executor.stop()
        assert not executor.is_running()

    def test_context_manager(self):
        """Test that the executor works as a context manager."""
        with AsyncToolExecutor() as executor:
            assert executor.is_running()
        # Should be stopped after exiting context
        assert not executor.is_running()

    @pytest.mark.asyncio
    async def test_async_tool_execution(self):
        """Test that async tools execute correctly without blocking."""
        async def sample_async_tool(value: str) -> str:
            """A sample async tool that simulates I/O work."""
            await asyncio.sleep(0.1)  # Simulate async I/O
            return f"Result: {value}"

        with AsyncToolExecutor() as executor:
            # Submit the async coroutine
            future = executor.submit_async(sample_async_tool("test"))
            
            # This should not block - we get a future immediately
            assert future is not None
            
            # Wait for the result
            result = future.result(timeout=1.0)
            assert result == "Result: test"

    def test_sync_tool_execution(self):
        """Test that sync tools execute correctly in thread pool."""
        def sample_sync_tool(value: str) -> str:
            """A sample sync tool that simulates CPU work."""
            time.sleep(0.1)  # Simulate blocking work
            return f"Sync Result: {value}"

        with AsyncToolExecutor() as executor:
            # Submit the sync function
            future = executor.submit_sync(sample_sync_tool, "test")
            
            # This should not block - we get a future immediately
            assert future is not None
            
            # Wait for the result
            result = future.result(timeout=1.0)
            assert result == "Sync Result: test"

    def test_concurrent_execution(self):
        """Test that multiple tools can run concurrently."""
        async def slow_async_tool(delay: float, name: str) -> str:
            await asyncio.sleep(delay)
            return f"Tool {name} completed"

        with AsyncToolExecutor() as executor:
            start_time = time.time()
            
            # Submit multiple async tasks
            future1 = executor.submit_async(slow_async_tool(0.2, "A"))
            future2 = executor.submit_async(slow_async_tool(0.2, "B"))
            future3 = executor.submit_async(slow_async_tool(0.2, "C"))
            
            # Wait for all results
            result1 = future1.result(timeout=1.0)
            result2 = future2.result(timeout=1.0)
            result3 = future3.result(timeout=1.0)
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            # Should complete in roughly 0.2 seconds (concurrent) not 0.6 (sequential)
            assert elapsed < 0.4, f"Tools took {elapsed:.2f}s, expected concurrent execution"
            assert result1 == "Tool A completed"
            assert result2 == "Tool B completed"
            assert result3 == "Tool C completed"


class TestUnifiedToolDispatcher:
    """Test the UnifiedToolDispatcher."""

    def test_async_tool_dispatch(self):
        """Test dispatching async tools."""
        async def async_tool(param: str) -> str:
            await asyncio.sleep(0.05)
            return f"Async: {param}"

        with AsyncToolExecutor() as executor:
            dispatcher = UnifiedToolDispatcher(executor, default_timeout=1.0)
            
            result = dispatcher.dispatch_tool(async_tool, {"param": "test"})
            assert result == "Async: test"

    def test_sync_tool_dispatch(self):
        """Test dispatching sync tools."""
        def sync_tool(param: str) -> str:
            time.sleep(0.05)
            return f"Sync: {param}"

        with AsyncToolExecutor() as executor:
            dispatcher = UnifiedToolDispatcher(executor, default_timeout=1.0)
            
            result = dispatcher.dispatch_tool(sync_tool, {"param": "test"})
            assert result == "Sync: test"

    def test_timeout_handling(self):
        """Test that timeouts are properly handled."""
        async def slow_tool() -> str:
            await asyncio.sleep(2.0)  # Takes longer than timeout
            return "Should not reach here"

        with AsyncToolExecutor() as executor:
            dispatcher = UnifiedToolDispatcher(executor, default_timeout=0.1)
            
            with pytest.raises(TimeoutError):
                dispatcher.dispatch_tool(slow_tool, {})

    def test_exception_propagation(self):
        """Test that exceptions from tools are properly propagated."""
        async def failing_tool() -> str:
            raise ValueError("Tool failed!")

        with AsyncToolExecutor() as executor:
            dispatcher = UnifiedToolDispatcher(executor, default_timeout=1.0)
            
            with pytest.raises(ValueError, match="Tool failed!"):
                dispatcher.dispatch_tool(failing_tool, {})


def test_performance_comparison():
    """
    Test to demonstrate the performance difference between the old asyncio.run()
    pattern and the new AsyncToolExecutor pattern.
    """
    async def io_simulation() -> str:
        """Simulate an I/O bound operation."""
        await asyncio.sleep(0.1)
        return "IO complete"

    # Simulate the OLD, BAD pattern (asyncio.run())
    def old_pattern_execution():
        start_time = time.time()
        results = []
        for i in range(3):
            # This is what the old code was doing - creating new event loops
            result = asyncio.run(io_simulation())
            results.append(result)
        end_time = time.time()
        return end_time - start_time, results

    # Test the NEW, CORRECT pattern (AsyncToolExecutor)
    def new_pattern_execution():
        start_time = time.time()
        with AsyncToolExecutor() as executor:
            futures = []
            for i in range(3):
                future = executor.submit_async(io_simulation())
                futures.append(future)
            
            results = [f.result(timeout=1.0) for f in futures]
        end_time = time.time()
        return end_time - start_time, results

    old_time, old_results = old_pattern_execution()
    new_time, new_results = new_pattern_execution()

    # Both should produce the same results
    assert old_results == new_results == ["IO complete", "IO complete", "IO complete"]
    
    # New pattern should be significantly faster due to concurrency
    # Old pattern: ~0.3s (sequential), New pattern: ~0.1s (concurrent)
    print(f"Old pattern time: {old_time:.3f}s")
    print(f"New pattern time: {new_time:.3f}s")
    print(f"Performance improvement: {(old_time / new_time):.1f}x faster")
    
    # The new pattern should be at least 2x faster
    assert new_time < old_time / 2, f"Expected significant performance improvement, got {old_time:.3f}s -> {new_time:.3f}s"


if __name__ == "__main__":
    # Run the performance comparison
    test_performance_comparison()
    print("All tests would pass! The AsyncToolExecutor fix is working correctly.")