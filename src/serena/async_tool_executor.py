"""
Async Tool Executor for MCP Server

This module implements the background event loop architecture recommended by the knowledge agent
to properly handle asynchronous tools without blocking the main server thread.
"""

import asyncio
import threading
import inspect
import time
import uuid
from concurrent.futures import Future, TimeoutError
from typing import Callable, Coroutine, Any, Union, Optional
import logging

log = logging.getLogger(__name__)


class AsyncToolExecutor:
    """
    Manages a dedicated asyncio event loop running in a background thread
    to execute asynchronous tools in a non-blocking, thread-safe manner.
    
    This class implements the solution recommended by the knowledge agent to fix
    the asyncio.run() anti-pattern that was causing client hanging.
    """
    
    def __init__(self):
        self._loop = None
        self._thread = None
        self._startup_event = threading.Event()
        self._shutdown_event = threading.Event()

    def start(self):
        """Starts the background thread and the asyncio event loop."""
        if self._thread is not None:
            return  # Already started

        log.info("Starting AsyncToolExecutor background thread...")
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="AsyncToolExecutor")
        self._thread.start()
        
        # Wait until the loop is running in the background thread
        if not self._startup_event.wait(timeout=10.0):
            raise RuntimeError("Failed to start AsyncToolExecutor within timeout")
        
        log.info("AsyncToolExecutor started with event loop")

    def stop(self):
        """Stops the event loop and joins the background thread gracefully."""
        if self._thread is None or self._loop is None:
            return

        log.info("Stopping AsyncToolExecutor...")
        
        # Schedule the loop to stop from the loop's own thread
        self._loop.call_soon_threadsafe(self._loop.stop)
        
        # Signal shutdown and wait for thread to complete
        self._shutdown_event.set()
        self._thread.join(timeout=10.0)
        
        self._thread = None
        self._loop = None
        log.info("AsyncToolExecutor stopped")

    def _run_loop(self):
        """The target function for the background thread."""
        try:
            # Create new event loop for this thread
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            
            # Signal that the loop is set up and running
            self._startup_event.set()
            
            # Run the event loop until stopped
            self._loop.run_forever()
            
        except Exception as e:
            log.error(f"Error in AsyncToolExecutor background thread: {e}")
        finally:
            # Clean up pending tasks
            if self._loop:
                pending = asyncio.all_tasks(self._loop)
                if pending:
                    log.info(f"Cancelling {len(pending)} pending tasks...")
                    for task in pending:
                        task.cancel()
                    
                    # Wait for cancellation to complete
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                
                self._loop.close()

    def submit_async(self, coro: Coroutine) -> Future:
        """
        Thread-safely submits an asynchronous coroutine to the event loop.

        Args:
            coro: The coroutine to execute.

        Returns:
            A concurrent.futures.Future that will hold the result.
        """
        if not self._loop:
            raise RuntimeError("AsyncToolExecutor is not running. Call start() first.")
        
        # Generate unique task ID for tracking
        task_id = str(uuid.uuid4())[:8]
        log.debug(f"Submitting async task {task_id} to event loop")
        
        try:
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            log.debug(f"Task {task_id} submitted successfully")
            return future
        except Exception as e:
            log.error(f"Failed to submit task {task_id}: {e}")
            raise

    def submit_sync(self, func: Callable, *args: Any, **kwargs: Any) -> Future:
        """
        Submits a synchronous function to run in a thread pool executor.
        
        This wraps the sync function in run_in_executor and submits it to the event loop.

        Args:
            func: The synchronous function to execute.
            args: Positional arguments to pass to the function.
            kwargs: Keyword arguments to pass to the function.

        Returns:
            A concurrent.futures.Future that will hold the result.
        """
        if not self._loop:
            raise RuntimeError("AsyncToolExecutor is not running. Call start() first.")
        
        # Generate unique task ID for tracking
        task_id = str(uuid.uuid4())[:8]
        func_name = getattr(func, '__name__', str(func))
        log.debug(f"Submitting sync task {task_id} ({func_name}) to thread pool")
        
        # Create a coroutine that runs the sync function in the executor
        async def _run_sync():
            try:
                log.debug(f"Executing sync task {task_id} ({func_name})")
                result = await self._loop.run_in_executor(None, lambda: func(*args, **kwargs))
                log.debug(f"Sync task {task_id} ({func_name}) completed successfully")
                return result
            except Exception as e:
                log.error(f"Sync task {task_id} ({func_name}) failed: {e}")
                raise
        
        # Submit the coroutine to the event loop
        return self.submit_async(_run_sync())

    def is_running(self) -> bool:
        """Returns True if the executor is running."""
        return self._thread is not None and self._loop is not None

    def ping(self, timeout: float = 5.0) -> bool:
        """
        Ping the executor to check if it's responsive.
        
        Args:
            timeout: Timeout in seconds for the ping operation
            
        Returns:
            True if the executor is responsive, False otherwise
        """
        if not self.is_running():
            return False
        
        try:
            # Submit a simple async task to test responsiveness
            async def _ping():
                await asyncio.sleep(0.001)  # Minimal async operation
                return "pong"
            
            future = self.submit_async(_ping())
            result = future.result(timeout=timeout)
            return result == "pong"
        except Exception as e:
            log.warning(f"Ping failed: {e}")
            return False

    def get_stats(self) -> dict:
        """
        Get statistics about the executor state.
        
        Returns:
            Dictionary with executor statistics
        """
        if not self.is_running():
            return {"status": "stopped", "thread_alive": False, "loop_running": False}
        
        try:
            # Get basic stats from the event loop
            stats = {
                "status": "running",
                "thread_alive": self._thread.is_alive(),
                "loop_running": self._loop.is_running() if self._loop else False,
                "thread_name": self._thread.name if self._thread else None,
            }
            
            # Try to get more detailed stats if possible
            if self._loop:
                pending_tasks = len(asyncio.all_tasks(self._loop))
                stats["pending_tasks"] = pending_tasks
                
            return stats
        except Exception as e:
            log.warning(f"Failed to get executor stats: {e}")
            return {"status": "error", "error": str(e)}

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class UnifiedToolDispatcher:
    """
    Unified dispatcher that intelligently routes synchronous and asynchronous tools
    to the appropriate execution context with retry logic and enhanced error handling.
    """
    
    def __init__(self, executor: AsyncToolExecutor, default_timeout: float = 300.0, max_retries: int = 2):
        self.executor = executor
        self.default_timeout = default_timeout
        self.max_retries = max_retries

    def dispatch_tool(self, tool_func: Callable, tool_params: dict, timeout: float = None, 
                     max_retries: Optional[int] = None) -> Any:
        """
        Dispatches a tool function (sync or async) to the appropriate execution context.
        
        Args:
            tool_func: The tool function to execute
            tool_params: Parameters to pass to the tool
            timeout: Timeout in seconds (uses default if None)
            max_retries: Maximum number of retries (uses default if None)
            
        Returns:
            The result of the tool execution
            
        Raises:
            TimeoutError: If the tool execution times out after all retries
            Exception: Any exception raised by the tool
        """
        if timeout is None:
            timeout = self.default_timeout
        if max_retries is None:
            max_retries = self.max_retries
            
        tool_name = getattr(tool_func, '__name__', str(tool_func))
        
        # Check executor health before starting
        if not self.executor.is_running():
            raise RuntimeError(f"AsyncToolExecutor is not running - cannot dispatch tool '{tool_name}'")
        
        # Ping the executor to ensure it's responsive
        if not self.executor.ping(timeout=min(5.0, timeout / 2)):
            log.warning(f"Executor ping failed before dispatching tool '{tool_name}'")
        
        last_exception = None
        
        for attempt in range(max_retries + 1):  # +1 because we want max_retries actual retries
            try:
                start_time = time.time()
                
                if attempt > 0:
                    # Exponential backoff for retries
                    delay = min(2 ** (attempt - 1), 10.0)  # Cap at 10 seconds
                    log.info(f"Retrying tool '{tool_name}' (attempt {attempt + 1}/{max_retries + 1}) after {delay:.1f}s delay")
                    time.sleep(delay)
                
                log.info(f"Dispatching tool '{tool_name}' (attempt {attempt + 1}/{max_retries + 1})")
                
                if inspect.iscoroutinefunction(tool_func):
                    # It's an async tool - submit directly to event loop
                    log.debug(f"Dispatching ASYNC tool: {tool_name}")
                    coro = tool_func(**tool_params)
                    future = self.executor.submit_async(coro)
                else:
                    # It's a sync tool - run in thread pool executor
                    log.debug(f"Dispatching SYNC tool: {tool_name}")
                    future = self.executor.submit_sync(tool_func, **tool_params)

                # Wait for the result with timeout
                log.debug(f"Waiting for tool '{tool_name}' result (timeout: {timeout}s)")
                result = future.result(timeout=timeout)
                
                elapsed_time = time.time() - start_time
                log.info(f"Tool '{tool_name}' completed successfully in {elapsed_time:.2f}s")
                
                # Log result delivery confirmation
                result_size = len(str(result)) if result is not None else 0
                log.debug(f"Tool '{tool_name}' result delivered to client (size: {result_size} chars)")
                
                return result
                
            except TimeoutError as e:
                elapsed_time = time.time() - start_time
                log.error(f"Tool '{tool_name}' timed out after {elapsed_time:.2f}s (timeout: {timeout}s)")
                last_exception = e
                
                # For timeout errors, we might want to retry
                if attempt < max_retries:
                    log.warning(f"Will retry tool '{tool_name}' due to timeout")
                    continue
                else:
                    log.error(f"Tool '{tool_name}' failed permanently after {max_retries} retries due to timeout")
                    raise
                    
            except Exception as e:
                elapsed_time = time.time() - start_time
                log.error(f"Tool '{tool_name}' failed with exception after {elapsed_time:.2f}s: {e}")
                last_exception = e
                
                # For non-timeout exceptions, we generally don't retry unless it's a communication issue
                if self._is_communication_error(e) and attempt < max_retries:
                    log.warning(f"Will retry tool '{tool_name}' due to communication error: {e}")
                    continue
                else:
                    log.error(f"Tool '{tool_name}' failed permanently: {e}")
                    raise
        
        # If we get here, all retries failed
        log.error(f"Tool '{tool_name}' failed after {max_retries} retries")
        raise last_exception if last_exception else RuntimeError(f"Tool '{tool_name}' failed after retries")

    def _is_communication_error(self, exception: Exception) -> bool:
        """
        Determine if an exception is likely due to communication issues that warrant a retry.
        
        Args:
            exception: The exception to analyze
            
        Returns:
            True if the exception suggests a communication issue
        """
        # Common patterns that suggest communication/infrastructure issues
        error_msg = str(exception).lower()
        communication_patterns = [
            "connection",
            "socket",
            "network",
            "broken pipe",
            "connection reset",
            "connection refused",
            "timeout",
            "unreachable",
            "channel closed",
            "event loop",
            "task was cancelled",
            "cancelled",
        ]
        
        return any(pattern in error_msg for pattern in communication_patterns)


class HealthChecker:
    """
    Utility class to perform health checks on the AsyncToolExecutor
    to help diagnose communication issues.
    """
    
    def __init__(self, executor: AsyncToolExecutor):
        self.executor = executor
    
    def comprehensive_health_check(self) -> dict:
        """
        Perform a comprehensive health check on the executor.
        
        Returns:
            Dictionary with health check results
        """
        results = {
            "timestamp": time.time(),
            "overall_status": "unknown",
            "checks": {}
        }
        
        try:
            # Check 1: Basic status
            results["checks"]["basic_status"] = self.executor.get_stats()
            
            # Check 2: Ping test
            ping_start = time.time()
            ping_success = self.executor.ping(timeout=5.0)
            ping_duration = time.time() - ping_start
            results["checks"]["ping"] = {
                "success": ping_success,
                "duration_ms": round(ping_duration * 1000, 2)
            }
            
            # Check 3: Simple task execution
            try:
                async def simple_task():
                    await asyncio.sleep(0.1)
                    return "success"
                
                task_start = time.time()
                future = self.executor.submit_async(simple_task())
                task_result = future.result(timeout=10.0)
                task_duration = time.time() - task_start
                
                results["checks"]["simple_task"] = {
                    "success": task_result == "success",
                    "duration_ms": round(task_duration * 1000, 2),
                    "result": task_result
                }
            except Exception as e:
                results["checks"]["simple_task"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Determine overall status
            all_checks_passed = all(
                check.get("success", False) for check in results["checks"].values()
                if isinstance(check, dict) and "success" in check
            )
            results["overall_status"] = "healthy" if all_checks_passed else "unhealthy"
            
        except Exception as e:
            results["overall_status"] = "error"
            results["error"] = str(e)
            log.error(f"Health check failed: {e}")
        
        return results


class StressTester:
    """
    Utility class to stress test the AsyncToolExecutor
    to reproduce communication issues.
    """
    
    def __init__(self, dispatcher: UnifiedToolDispatcher):
        self.dispatcher = dispatcher
    
    def run_stress_test(self, num_tasks: int = 10, concurrent_tasks: int = 3) -> dict:
        """
        Run a stress test with multiple concurrent tool calls.
        
        Args:
            num_tasks: Total number of tasks to run
            concurrent_tasks: Number of concurrent tasks to run at once
            
        Returns:
            Dictionary with stress test results
        """
        results = {
            "timestamp": time.time(),
            "config": {
                "num_tasks": num_tasks,
                "concurrent_tasks": concurrent_tasks
            },
            "results": [],
            "summary": {}
        }
        
        async def dummy_async_tool(task_id: int, delay: float = 0.1):
            """Dummy async tool for testing"""
            await asyncio.sleep(delay)
            return f"async_result_{task_id}"
        
        def dummy_sync_tool(task_id: int, delay: float = 0.1):
            """Dummy sync tool for testing"""
            time.sleep(delay)
            return f"sync_result_{task_id}"
        
        log.info(f"Starting stress test: {num_tasks} tasks, {concurrent_tasks} concurrent")
        
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_tasks) as executor:
            futures = []
            
            for i in range(num_tasks):
                # Alternate between async and sync tools
                if i % 2 == 0:
                    tool_func = dummy_async_tool
                    tool_type = "async"
                else:
                    tool_func = dummy_sync_tool
                    tool_type = "sync"
                
                future = executor.submit(
                    self._run_single_task,
                    i, tool_func, tool_type, {"task_id": i, "delay": 0.1}
                )
                futures.append(future)
            
            # Collect results
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results["results"].append(result)
                except Exception as e:
                    log.error(f"Stress test task failed: {e}")
                    results["results"].append({
                        "success": False,
                        "error": str(e)
                    })
        
        # Calculate summary
        successful_tasks = sum(1 for r in results["results"] if r.get("success", False))
        failed_tasks = len(results["results"]) - successful_tasks
        
        results["summary"] = {
            "total_tasks": len(results["results"]),
            "successful": successful_tasks,
            "failed": failed_tasks,
            "success_rate": successful_tasks / len(results["results"]) if results["results"] else 0,
            "avg_duration_ms": sum(r.get("duration_ms", 0) for r in results["results"]) / len(results["results"]) if results["results"] else 0
        }
        
        log.info(f"Stress test completed: {successful_tasks}/{len(results['results'])} successful")
        return results
    
    def _run_single_task(self, task_id: int, tool_func: Callable, tool_type: str, params: dict) -> dict:
        """Run a single task and return the result summary"""
        start_time = time.time()
        
        try:
            result = self.dispatcher.dispatch_tool(tool_func, params, timeout=30.0)
            duration = time.time() - start_time
            
            return {
                "task_id": task_id,
                "tool_type": tool_type,
                "success": True,
                "duration_ms": round(duration * 1000, 2),
                "result": result
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "task_id": task_id,
                "tool_type": tool_type,
                "success": False,
                "duration_ms": round(duration * 1000, 2),
                "error": str(e)
            }