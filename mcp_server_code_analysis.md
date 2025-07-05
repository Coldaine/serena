# MCP Server Code Analysis for Async Tool Improvements

## Current Architecture Overview

This document contains the key code snippets from our MCP server implementation that are relevant to improving asynchronous tool capabilities.

## 1. AsyncTool Base Class Implementation

```python
class AsyncTool(Component, ToolInterface):
    """
    Base class for asynchronous tools that support progress callbacks.
    These tools yield control during I/O operations to keep the server responsive.
    """

    async def get_apply_fn(self) -> Callable:
        apply_fn = getattr(self, "apply_async")
        if apply_fn is None:
            raise RuntimeError(f"apply_async not defined in {self}. Did you forget to implement it?")
        return apply_fn

    def apply_ex(self, log_call: bool = True, catch_exceptions: bool = True, **kwargs) -> str:
        """
        Synchronous wrapper for async tools - runs the async apply_async method.
        """
        async def task() -> str:
            # Add default progress callback if none provided
            if "progress_callback" not in kwargs:
                kwargs["progress_callback"] = self._default_progress_callback

            apply_fn = await self.get_apply_fn()
            
            # ... validation and setup code ...
            
            # apply the actual async tool
            result = await apply_fn(**kwargs)
            
            # ... cleanup code ...
            return result

        # PROBLEM: Running async task in synchronous context
        future = self.agent.issue_task(lambda: asyncio.run(task()), name=self.__class__.__name__)
        return future.result(timeout=self.agent.serena_config.tool_timeout)
```

## 2. Example AsyncTool Implementation

```python
class AsyncReadFileTool(AsyncTool):
    """
    Asynchronously reads a file within the project directory with progress reporting.
    """

    async def apply_async(
        self,
        relative_path: str,
        start_line: int = 0,
        end_line: int | None = None,
        max_answer_chars: int = 200000,
        progress_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """
        Reads the given file or a chunk of it.
        """
        if progress_callback is None:
            progress_callback = self._default_progress_callback

        await progress_callback(f"Reading file: {relative_path}")
        
        # ... actual async file reading implementation ...
        
        return self._limit_length(result, max_answer_chars)
```

## 3. MCP Tool Factory - THE CORE PROBLEM

```python
class SerenaMCPFactory:
    @staticmethod
    def make_mcp_tool(tool: ToolInterface) -> MCPTool:
        func_name = tool.get_name()
        func_doc = tool.get_apply_docstring() or ""
        func_arg_metadata = tool.get_apply_fn_metadata()
        
        # PROBLEM: Hardcoded to False even for AsyncTools!
        is_async = False
        
        parameters = func_arg_metadata.arg_model.model_json_schema()

        # ... docstring processing ...

        def execute_fn(**kwargs) -> str:
            return tool.apply_ex(log_call=True, catch_exceptions=True, **kwargs)

        return MCPTool(
            fn=execute_fn,
            name=func_name,
            description=func_doc,
            parameters=parameters,
            fn_metadata=func_arg_metadata,
            is_async=is_async,  # Always False!
            context_kwarg=None,
            annotations=None,
        )
```

## 4. Process Isolated Tool Execution

```python
class ProcessIsolatedTool(ToolInterface):
    """A clean tool wrapper that delegates to ProcessIsolatedSerenaAgent."""

    def apply_ex(self, log_call: bool = True, catch_exceptions: bool = True, **kwargs: Any) -> str:
        """Apply the tool with logging and exception handling."""
        try:
            return self.process_agent.tool_call(self._tool_name, **kwargs)
        except Exception as e:
            if catch_exceptions:
                return f"Error executing tool {self._tool_name}: {e!s}"
            raise

class ProcessIsolatedSerenaAgent:
    def tool_call(self, tool_name: str, **tool_params: Any) -> str:
        """Call a tool in the worker process."""
        return self._make_request_with_result(
            SerenaAgentWorker.RequestMethod.TOOL_CALL, 
            {"tool_name": tool_name, "tool_params": tool_params}
        )

    def _make_request(self, method: SerenaAgentWorker.RequestMethod, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a request to the worker process."""
        # ... connection setup ...
        
        request = {"method": method, "params": params or {}}
        
        # Send request
        self.conn.send(request)
        
        # Wait for response with timeout
        timeout = self.serena_config.tool_timeout
        if self.conn.poll(timeout):
            return self.conn.recv()
        else:
            raise TimeoutError(f"Request {method} timed out after {timeout} seconds")
```

## 5. Tool Registry - Async Tool Detection

```python
def _iter_tool_classes(same_module_only: bool = True) -> Iterator[type[Tool] | type[AsyncTool]]:
    # Iterate over Tool subclasses
    for tool_class in iter_subclasses(Tool):
        if same_module_only and tool_class.__module__ != Tool.__module__:
            continue
        yield tool_class
    
    # Iterate over AsyncTool subclasses
    for tool_class in iter_subclasses(AsyncTool):
        if same_module_only and tool_class.__module__ != AsyncTool.__module__:
            continue
        yield tool_class

_TOOL_REGISTRY_DICT: dict[str, type[Tool] | type[AsyncTool]] = {
    tool_class.get_name_from_cls(): tool_class 
    for tool_class in _iter_tool_classes()
}

class ToolRegistry:
    @staticmethod
    def get_tool_class_by_name(tool_name: str) -> type[Tool] | type[AsyncTool]:
        return _TOOL_REGISTRY_DICT[tool_name]
```

## 6. Agent Tool Management

```python
class SerenaAgent:
    def __init__(self, ...):
        # instantiate all tool classes (both regular Tool and AsyncTool)
        self._all_tools: dict[type[Tool] | type[AsyncTool], Tool | AsyncTool] = {
            tool_class: tool_class(self) 
            for tool_class in ToolRegistry.get_all_tool_classes()
        }

    def get_active_tool_classes(self) -> list[type["Tool"] | type["AsyncTool"]]:
        """
        :return: the list of active tool classes for the current project
        """
        return list(self._active_tools.keys())

    def tool_is_active(self, tool_class: type["Tool"] | type["AsyncTool"] | str) -> bool:
        # ... implementation ...
```

## 7. Configuration & Timeouts

```python
class SerenaConfig:
    def __init__(self):
        # ...
        self.tool_timeout = loaded_commented_yaml.get("tool_timeout", DEFAULT_TOOL_TIMEOUT)

# In agent.py
DEFAULT_TOOL_TIMEOUT = 300  # 5 minutes

# In process isolated agent
def _make_request(self, ...):
    timeout = self.serena_config.tool_timeout
    if self.conn.poll(timeout):
        return self.conn.recv()
    else:
        raise TimeoutError(f"Request {method} timed out after {timeout} seconds")
```

## Key Issues Identified

1. **is_async Always False**: Both `SerenaMCPFactory.make_mcp_tool()` and `SerenaMCPFactoryWithProcessIsolation.make_mcp_tool()` hardcode `is_async = False`

2. **Synchronous Wrapper**: AsyncTool uses `asyncio.run()` in `apply_ex()`, which blocks the thread

3. **No Type Detection**: The MCP factory doesn't check if the tool is an AsyncTool instance

4. **Process Isolation Complexity**: Process-isolated tools add another layer that may interfere with async execution

5. **Timeout Misalignment**: Tool timeouts may not account for async operation patterns

## Potential Solutions to Research

1. **Dynamic is_async Detection**:
```python
is_async = isinstance(tool, AsyncTool)
```

2. **Proper Async Execution**: Instead of `asyncio.run()`, use proper async context

3. **Concurrent Tool Execution**: Allow multiple async tools to run concurrently

4. **Progress Streaming**: Implement real-time progress updates through MCP protocol

5. **Timeout Optimization**: Adjust timeout handling for async vs sync tools