"""
Async Tool Executor for MCP Server

This module implements the background event loop architecture recommended by the knowledge agent
to properly handle asynchronous tools without blocking the main server thread.
"""

import asyncio
import threading
import inspect
from concurrent.futures import Future
from typing import Callable, Coroutine, Any, Union
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
        
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

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
        
        # Create a coroutine that runs the sync function in the executor
        async def _run_sync():
            return await self._loop.run_in_executor(None, lambda: func(*args, **kwargs))
        
        # Submit the coroutine to the event loop
        return self.submit_async(_run_sync())

    def is_running(self) -> bool:
        """Returns True if the executor is running."""
        return self._thread is not None and self._loop is not None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class UnifiedToolDispatcher:
    """
    Unified dispatcher that intelligently routes synchronous and asynchronous tools
    to the appropriate execution context.
    """
    
    def __init__(self, executor: AsyncToolExecutor, default_timeout: float = 300.0):
        self.executor = executor
        self.default_timeout = default_timeout

    def dispatch_tool(self, tool_func: Callable, tool_params: dict, timeout: float = None) -> Any:
        """
        Dispatches a tool function (sync or async) to the appropriate execution context.
        
        Args:
            tool_func: The tool function to execute
            tool_params: Parameters to pass to the tool
            timeout: Timeout in seconds (uses default if None)
            
        Returns:
            The result of the tool execution
            
        Raises:
            TimeoutError: If the tool execution times out
            Exception: Any exception raised by the tool
        """
        if timeout is None:
            timeout = self.default_timeout
            
        tool_name = getattr(tool_func, '__name__', str(tool_func))
        
        try:
            if inspect.iscoroutinefunction(tool_func):
                # It's an async tool - submit directly to event loop
                log.info(f"Dispatching ASYNC tool: {tool_name}")
                coro = tool_func(**tool_params)
                future = self.executor.submit_async(coro)
            else:
                # It's a sync tool - run in thread pool executor
                log.info(f"Dispatching SYNC tool: {tool_name}")
                future = self.executor.submit_sync(tool_func, **tool_params)

            # Wait for the result with timeout
            result = future.result(timeout=timeout)
            log.info(f"Tool '{tool_name}' completed successfully")
            return result
            
        except TimeoutError as e:
            log.error(f"Tool '{tool_name}' timed out after {timeout} seconds")
            raise
        except Exception as e:
            log.error(f"Tool '{tool_name}' failed with exception: {e}")
            raise