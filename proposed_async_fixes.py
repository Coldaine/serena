#!/usr/bin/env python3
"""
Proposed fixes for async tool silent failures.
This demonstrates how to add error handling wrappers and validation.
"""
import asyncio
import logging
import functools
import json
from typing import Callable, Any, Awaitable, Optional, Dict
from pathlib import Path


class AsyncToolErrorHandler:
    """Enhanced error handling for async tools"""
    
    def __init__(self, timeout_default: float = 30.0):
        self.timeout_default = timeout_default
        self.logger = logging.getLogger(__name__)
    
    def with_error_handling(self, timeout: Optional[float] = None):
        """Decorator to add comprehensive error handling to async tools"""
        
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(*args, **kwargs) -> str:
                tool_name = func.__name__
                actual_timeout = timeout or self.timeout_default
                
                try:
                    # Validate basic inputs
                    self._validate_inputs(kwargs)
                    
                    self.logger.debug(f"Starting {tool_name} with timeout {actual_timeout}s")
                    
                    # Execute with timeout protection
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=actual_timeout
                    )
                    
                    # Validate output
                    validated_result = self._validate_output(result, tool_name)
                    
                    self.logger.debug(f"Completed {tool_name} successfully")
                    return validated_result
                    
                except asyncio.TimeoutError:
                    error_msg = f"Error: {tool_name} timed out after {actual_timeout}s"
                    self.logger.error(error_msg)
                    return error_msg
                    
                except Exception as e:
                    error_msg = f"Error: {tool_name} failed - {type(e).__name__}: {str(e)}"
                    self.logger.error(error_msg)
                    return error_msg
            
            return wrapper
        return decorator
    
    def _validate_inputs(self, kwargs: Dict[str, Any]) -> None:
        """Validate common input parameters"""
        
        # Check for empty or None relative_path
        if 'relative_path' in kwargs:
            path = kwargs['relative_path']
            if path is None:
                raise ValueError("relative_path cannot be None")
            if path == "":
                raise ValueError("relative_path cannot be empty")
        
        # Check for None content
        if 'content' in kwargs:
            content = kwargs['content']
            if content is None:
                raise ValueError("content cannot be None")
        
        # Check for empty command
        if 'command' in kwargs:
            command = kwargs['command']
            if command is None:
                raise ValueError("command cannot be None")
            if command == "":
                raise ValueError("command cannot be empty")
    
    def _validate_output(self, result: Any, tool_name: str) -> str:
        """Validate and normalize tool output"""
        
        if result is None:
            return f"Error: {tool_name} returned None"
        
        if result == "":
            return f"Error: {tool_name} returned empty result"
        
        # Ensure we always return a string
        return str(result)


# Example usage - Enhanced MCP tool implementations

error_handler = AsyncToolErrorHandler(timeout_default=30.0)


@error_handler.with_error_handling(timeout=15.0)
async def enhanced_async_read_file(relative_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """Enhanced async read file with comprehensive error handling"""
    
    # Import here to avoid circular imports
    from serena.agent import get_or_create_agent, AsyncReadFileTool
    
    try:
        agent = await get_or_create_agent()
        tool = AsyncReadFileTool(agent)
        
        # Add progress callback for monitoring
        async def progress_callback(message: str) -> None:
            logging.debug(f"Progress: {message}")
        
        result = await tool.apply_async(
            relative_path=relative_path,
            start_line=start_line,
            end_line=end_line,
            progress_callback=progress_callback
        )
        
        return result
        
    except FileNotFoundError:
        return f"Error: FileNotFoundError - File not found: {relative_path}"
    except PermissionError:
        return f"Error: PermissionError - Permission denied: {relative_path}"
    except Exception as e:
        return f"Error: Unexpected error reading file: {type(e).__name__}: {str(e)}"


@error_handler.with_error_handling(timeout=20.0)
async def enhanced_async_create_text_file(relative_path: str, content: str) -> str:
    """Enhanced async create file with comprehensive error handling"""
    
    from serena.agent import get_or_create_agent, AsyncCreateTextFileTool
    
    try:
        # Additional validation
        if len(relative_path) > 255:
            return "Error: Filename too long (max 255 characters)"
        
        # Check for invalid filename characters (Windows-style)
        invalid_chars = '<>:"|?*'
        if any(char in relative_path for char in invalid_chars):
            return f"Error: Invalid characters in filename: {relative_path}"
        
        agent = await get_or_create_agent()
        tool = AsyncCreateTextFileTool(agent)
        
        async def progress_callback(message: str) -> None:
            logging.debug(f"Progress: {message}")
        
        result = await tool.apply_async(
            relative_path=relative_path,
            content=content,
            progress_callback=progress_callback
        )
        
        return result
        
    except PermissionError:
        return f"Error: PermissionError - Permission denied: {relative_path}"
    except OSError as e:
        return f"Error: OSError - Cannot create file: {str(e)}"
    except Exception as e:
        return f"Error: Unexpected error creating file: {type(e).__name__}: {str(e)}"


@error_handler.with_error_handling(timeout=60.0)
async def enhanced_async_execute_shell_command(command: str, cwd: Optional[str] = None, capture_stderr: bool = True) -> str:
    """Enhanced async shell command with comprehensive error handling"""
    
    from serena.agent import get_or_create_agent, AsyncExecuteShellCommandTool
    
    try:
        # Additional validation
        if len(command) > 10000:
            return json.dumps({
                "return_code": -1,
                "stdout": "",
                "stderr": "Error: Command too long (max 10000 characters)"
            })
        
        agent = await get_or_create_agent()
        tool = AsyncExecuteShellCommandTool(agent)
        
        async def progress_callback(message: str) -> None:
            logging.debug(f"Progress: {message}")
        
        result = await tool.apply_async(
            command=command,
            cwd=cwd,
            capture_stderr=capture_stderr,
            progress_callback=progress_callback
        )
        
        # Ensure result is valid JSON
        if isinstance(result, str):
            try:
                json.loads(result)  # Validate JSON
                return result
            except json.JSONDecodeError:
                return json.dumps({
                    "return_code": -1,
                    "stdout": "",
                    "stderr": f"Error: Invalid JSON response: {result}"
                })
        else:
            return json.dumps({
                "return_code": -1,
                "stdout": "",
                "stderr": f"Error: Non-string response: {type(result)}"
            })
        
    except Exception as e:
        return json.dumps({
            "return_code": -1,
            "stdout": "",
            "stderr": f"Error: Unexpected error executing command: {type(e).__name__}: {str(e)}"
        })


class AsyncToolMonitor:
    """Monitor async tool executions to detect silent failures"""
    
    def __init__(self):
        self.active_tools: Dict[str, Dict[str, Any]] = {}
        self.completed_tools: Dict[str, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)
        
    async def track_execution(self, tool_name: str, coro: Awaitable, timeout: float = 30.0):
        """Track and monitor async tool execution"""
        tool_id = f"{tool_name}_{id(coro)}"
        start_time = asyncio.get_event_loop().time()
        
        async with self.lock:
            self.active_tools[tool_id] = {
                'name': tool_name,
                'start_time': start_time,
                'status': 'running'
            }
        
        try:
            # Create monitoring task
            monitor_task = asyncio.create_task(self._monitor_tool(tool_id, timeout))
            
            # Execute the actual tool
            result = await coro
            
            # Mark as completed
            async with self.lock:
                if tool_id in self.active_tools:
                    self.active_tools[tool_id]['status'] = 'completed'
                    self.active_tools[tool_id]['result'] = result
                    self.completed_tools[tool_id] = self.active_tools.pop(tool_id)
                    
            monitor_task.cancel()
            
            # Validate result
            if result is None:
                self.logger.warning(f"Tool {tool_name} returned None")
            elif result == "":
                self.logger.warning(f"Tool {tool_name} returned empty string")
            
            return result
            
        except Exception as e:
            async with self.lock:
                if tool_id in self.active_tools:
                    self.active_tools[tool_id]['status'] = 'failed'
                    self.active_tools[tool_id]['error'] = str(e)
                    self.completed_tools[tool_id] = self.active_tools.pop(tool_id)
            raise
        finally:
            async with self.lock:
                self.active_tools.pop(tool_id, None)
                
    async def _monitor_tool(self, tool_id: str, max_duration: float):
        """Monitor a specific tool execution"""
        check_interval = min(5.0, max_duration / 10)
        
        while True:
            await asyncio.sleep(check_interval)
            async with self.lock:
                if tool_id in self.active_tools:
                    tool_info = self.active_tools[tool_id]
                    elapsed = asyncio.get_event_loop().time() - tool_info['start_time']
                    
                    if elapsed > max_duration * 0.8:  # Warn at 80% of timeout
                        self.logger.warning(f"Tool {tool_info['name']} has been running for {elapsed:.1f}s (timeout: {max_duration}s)")
                    else:
                        self.logger.debug(f"Tool {tool_info['name']} still running after {elapsed:.1f}s")
                else:
                    break
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of monitored tools"""
        return {
            'active_count': len(self.active_tools),
            'completed_count': len(self.completed_tools),
            'active_tools': list(self.active_tools.keys()),
            'failed_tools': [
                tool_id for tool_id, info in self.completed_tools.items()
                if info['status'] == 'failed'
            ]
        }


# Example integration with MCP server
def create_enhanced_mcp_tools():
    """Create MCP tools with enhanced error handling"""
    
    # This would be used in the actual MCP server setup
    tools = {
        'async_read_file': enhanced_async_read_file,
        'async_create_text_file': enhanced_async_create_text_file,
        'async_execute_shell_command': enhanced_async_execute_shell_command,
    }
    
    return tools


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.DEBUG)
    
    async def test_enhanced_tools():
        """Test the enhanced tools"""
        
        print("🧪 Testing Enhanced Async Tools")
        print("=" * 40)
        
        # Test cases that would cause silent failures
        test_cases = [
            (enhanced_async_read_file, {"relative_path": ""}, "Empty path"),
            (enhanced_async_read_file, {"relative_path": "nonexistent.txt"}, "Non-existent file"),
            (enhanced_async_create_text_file, {"relative_path": "test.txt", "content": "test"}, "Valid file"),
            (enhanced_async_create_text_file, {"relative_path": "<>:|?*.txt", "content": "test"}, "Invalid filename"),
            (enhanced_async_execute_shell_command, {"command": "echo test"}, "Valid command"),
            (enhanced_async_execute_shell_command, {"command": ""}, "Empty command"),
        ]
        
        for func, kwargs, description in test_cases:
            print(f"\n🔧 Testing {func.__name__}: {description}")
            try:
                result = await func(**kwargs)
                print(f"   Result: {result[:100]}...")
                
                if result.startswith("Error:"):
                    print("   ✅ Error handled gracefully")
                else:
                    print("   ✅ Executed successfully")
                    
            except Exception as e:
                print(f"   ❌ Unexpected exception: {e}")
    
    asyncio.run(test_enhanced_tools())
