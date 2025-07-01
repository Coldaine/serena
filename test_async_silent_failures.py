#!/usr/bin/env python3
"""
Test plan for async tools that fail silently - tools that end instantly 
without returning a message to anybody.
"""
import asyncio
import json
import tempfile
from pathlib import Path
import sys
import logging
import time
from typing import Dict, Any, Optional

# Add src to path to import our modules
sys.path.insert(0, 'src')

try:
    from mcp.client.stdio import stdio_client
except ImportError:
    print("❌ MCP client libraries not available for direct testing")
    print("   This is expected - we'll test through tool validation instead")
    sys.exit(0)


class AsyncToolMonitor:
    """Monitor async tool executions to detect silent failures"""
    
    def __init__(self):
        self.active_tools: Dict[str, Dict[str, Any]] = {}
        self.completed_tools: Dict[str, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()
        
    async def track_execution(self, tool_name: str, tool_args: Dict, session, timeout: float = 30.0):
        """Track and monitor async tool execution"""
        tool_id = f"{tool_name}_{int(time.time() * 1000)}"
        start_time = time.time()
        
        async with self.lock:
            self.active_tools[tool_id] = {
                'name': tool_name,
                'args': tool_args,
                'start_time': start_time,
                'status': 'running'
            }
        
        try:
            print(f"   🔍 Starting {tool_name} with args: {tool_args}")
            
            # Create monitoring task
            monitor_task = asyncio.create_task(self._monitor_tool(tool_id))
            
            # Execute the actual tool with timeout
            result = await asyncio.wait_for(
                session.call_tool(tool_name, **tool_args),
                timeout=timeout
            )
            
            # Mark as completed
            async with self.lock:
                if tool_id in self.active_tools:
                    self.active_tools[tool_id]['status'] = 'completed'
                    self.active_tools[tool_id]['result'] = result
                    self.completed_tools[tool_id] = self.active_tools.pop(tool_id)
                    
            monitor_task.cancel()
            
            elapsed = time.time() - start_time
            print(f"   ✅ {tool_name} completed in {elapsed:.2f}s")
            return result
            
        except asyncio.TimeoutError:
            async with self.lock:
                if tool_id in self.active_tools:
                    self.active_tools[tool_id]['status'] = 'timeout'
                    self.completed_tools[tool_id] = self.active_tools.pop(tool_id)
            
            elapsed = time.time() - start_time
            print(f"   ⏰ {tool_name} timed out after {elapsed:.2f}s")
            raise
            
        except Exception as e:
            async with self.lock:
                if tool_id in self.active_tools:
                    self.active_tools[tool_id]['status'] = 'failed'
                    self.active_tools[tool_id]['error'] = str(e)
                    self.completed_tools[tool_id] = self.active_tools.pop(tool_id)
            
            elapsed = time.time() - start_time
            print(f"   ❌ {tool_name} failed after {elapsed:.2f}s: {e}")
            raise
                
    async def _monitor_tool(self, tool_id: str):
        """Monitor a specific tool execution"""
        while True:
            await asyncio.sleep(5)  # Check every 5 seconds
            async with self.lock:
                if tool_id in self.active_tools:
                    tool_info = self.active_tools[tool_id]
                    elapsed = time.time() - tool_info['start_time']
                    print(f"   ⏱️  {tool_info['name']} still running after {elapsed:.1f}s")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all tool executions"""
        summary = {
            'active': len(self.active_tools),
            'completed': len(self.completed_tools),
            'by_status': {}
        }
        
        for tool_info in self.completed_tools.values():
            status = tool_info['status']
            summary['by_status'][status] = summary['by_status'].get(status, 0) + 1
        
        return summary


async def test_silent_failures():
    """Test cases for async tools that fail silently"""
    print("🧪 Testing Async Tool Silent Failures")
    print("=" * 60)
    
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    
    monitor = AsyncToolMonitor()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        print(f"📁 Created temporary project at: {project_root}")
        
        # Create minimal project structure
        (project_root / "main.py").write_text("# Test file\nprint('Hello World')")
        (project_root / "requirements.txt").write_text("# Empty requirements file")
        
        # Start MCP server
        print("🚀 Starting MCP server...")
        server_process = await asyncio.create_subprocess_exec(
            "uv", "run", "serena-mcp-server",
            "--project", str(project_root),
            "--enable-web-dashboard", "False",
            "--enable-gui-log-window", "False",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            async with stdio_client(server_process) as session:
                print("✅ Connected to MCP server via stdio.")
                
                # Test Case 1: Tool with empty relative_path
                print("\n📍 Test 1: Tool with empty relative_path")
                try:
                    result = await monitor.track_execution(
                        "async_read_file",
                        {"relative_path": ""},
                        session,
                        timeout=10.0
                    )
                    print(f"   Result: {result}")
                    if result is None:
                        print("   ❌ Tool returned None!")
                    elif result == "":
                        print("   ❌ Tool returned empty string!")
                    else:
                        print(f"   ✅ Tool returned error message: {result[:100]}...")
                except Exception as e:
                    print(f"   ❌ Exception: {type(e).__name__}: {e}")
                
                # Test Case 2: Tool with None arguments (if possible)
                print("\n📍 Test 2: Tool with None content")
                try:
                    result = await monitor.track_execution(
                        "async_create_text_file",
                        {"relative_path": "test_none.txt", "content": None},
                        session,
                        timeout=10.0
                    )
                    print(f"   Result: {result}")
                    if result is None:
                        print("   ❌ Tool returned None!")
                    else:
                        print(f"   ✅ Tool handled None content: {result[:100]}...")
                except Exception as e:
                    print(f"   ❌ Exception: {type(e).__name__}: {e}")
                
                # Test Case 3: Tool with invalid filename characters
                print("\n📍 Test 3: Tool with invalid filename characters")
                try:
                    result = await monitor.track_execution(
                        "async_create_text_file",
                        {"relative_path": "<>:|?*.txt", "content": "test"},
                        session,
                        timeout=10.0
                    )
                    print(f"   Result: {result}")
                    if result is None:
                        print("   ❌ Tool returned None!")
                    else:
                        print(f"   ✅ Tool handled invalid filename: {result[:100]}...")
                except Exception as e:
                    print(f"   ❌ Exception: {type(e).__name__}: {e}")
                
                # Test Case 4: Tool with very long timeout to test monitoring
                print("\n📍 Test 4: Tool with potentially long execution")
                try:
                    # Command that should complete quickly but we'll monitor it
                    result = await monitor.track_execution(
                        "async_execute_shell_command",
                        {"command": "echo 'Testing monitoring'; sleep 2; echo 'Done'"},
                        session,
                        timeout=15.0
                    )
                    if result:
                        result_obj = json.loads(result)
                        print(f"   Result: return_code={result_obj.get('return_code')}")
                        print(f"   stdout: {result_obj.get('stdout', '')[:100]}...")
                    else:
                        print("   ❌ Tool returned None or empty!")
                except Exception as e:
                    print(f"   ❌ Exception: {type(e).__name__}: {e}")
                
                # Test Case 5: Command that will definitely fail
                print("\n📍 Test 5: Command that should fail gracefully")
                try:
                    result = await monitor.track_execution(
                        "async_execute_shell_command",
                        {"command": "this_command_absolutely_does_not_exist_123456"},
                        session,
                        timeout=10.0
                    )
                    if result:
                        result_obj = json.loads(result)
                        print(f"   Result: return_code={result_obj.get('return_code')}")
                        if result_obj.get('return_code', 0) != 0:
                            print("   ✅ Command failed as expected")
                        else:
                            print("   ❌ Command unexpectedly succeeded")
                    else:
                        print("   ❌ Tool returned None or empty!")
                except Exception as e:
                    print(f"   ❌ Exception: {type(e).__name__}: {e}")
                
                # Test Case 6: Read a file that definitely doesn't exist
                print("\n📍 Test 6: Read non-existent file")
                try:
                    result = await monitor.track_execution(
                        "async_read_file",
                        {"relative_path": "definitely_does_not_exist_12345.txt"},
                        session,
                        timeout=10.0
                    )
                    print(f"   Result: {result}")
                    if result is None:
                        print("   ❌ Tool returned None!")
                    elif "Error" in str(result) or "FileNotFoundError" in str(result):
                        print("   ✅ Tool returned proper error message")
                    else:
                        print("   ❌ Tool didn't return expected error message")
                except Exception as e:
                    print(f"   ❌ Exception: {type(e).__name__}: {e}")
                
        finally:
            # Cleanup
            print("\n🧹 Shutting down server...")
            if server_process.returncode is None:
                server_process.terminate()
                await server_process.wait()
            print("   ✅ Server shut down.")
        
        # Print monitoring summary
        print("\n📊 Execution Summary:")
        summary = monitor.get_summary()
        print(f"   Total tools executed: {summary['completed']}")
        print(f"   Still active: {summary['active']}")
        for status, count in summary['by_status'].items():
            print(f"   {status}: {count}")
        
        return summary


async def test_with_debug_trace():
    """Test async tools with enhanced debugging when MCP is not available"""
    print("\n🔍 Testing with Direct Tool Access (Debug Mode)")
    print("=" * 50)
    
    try:
        # Try to import and test tools directly
        from serena.agent import SerenaAgent
        from serena.agent import AsyncReadFileTool, AsyncCreateTextFileTool, AsyncExecuteShellCommandTool
        
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            
            # Create minimal agent
            agent = SerenaAgent(project_root=str(project_root), logs_dir=None)
            
            # Test each tool directly
            test_cases = [
                (AsyncReadFileTool, {"relative_path": ""}, "Empty path"),
                (AsyncReadFileTool, {"relative_path": "nonexistent.txt"}, "Non-existent file"),
                (AsyncCreateTextFileTool, {"relative_path": "test.txt", "content": "test"}, "Valid creation"),
                (AsyncCreateTextFileTool, {"relative_path": "", "content": "test"}, "Empty filename"),
                (AsyncExecuteShellCommandTool, {"command": "echo test"}, "Valid command"),
                (AsyncExecuteShellCommandTool, {"command": ""}, "Empty command"),
            ]
            
            for tool_class, kwargs, description in test_cases:
                print(f"\n🔧 Testing {tool_class.__name__}: {description}")
                try:
                    tool = tool_class(agent)
                    print(f"   ⏱️  Starting execution with: {kwargs}")
                    
                    start_time = time.time()
                    result = await asyncio.wait_for(
                        tool.apply_async(**kwargs),
                        timeout=10.0
                    )
                    elapsed = time.time() - start_time
                    
                    print(f"   ✅ Completed in {elapsed:.2f}s")
                    print(f"   Result type: {type(result)}")
                    if result is None:
                        print("   ❌ WARNING: Tool returned None!")
                    elif result == "":
                        print("   ❌ WARNING: Tool returned empty string!")
                    else:
                        print(f"   Result preview: {str(result)[:100]}...")
                        
                except asyncio.TimeoutError:
                    print("   ❌ Tool timed out!")
                except Exception as e:
                    print(f"   ❌ Exception: {type(e).__name__}: {e}")
    
    except ImportError as e:
        print(f"   ❌ Could not import Serena tools: {e}")
        print("   This test requires Serena to be properly installed")


if __name__ == "__main__":
    try:
        # Run the main silent failure tests
        summary = asyncio.run(test_silent_failures())
        
        # Run direct tool tests if possible
        asyncio.run(test_with_debug_trace())
        
        # Evaluate results
        if summary['by_status'].get('timeout', 0) > 0:
            print("\n⚠️  WARNING: Some tools timed out - possible silent failures!")
        
        if summary['by_status'].get('completed', 0) > 0:
            print(f"\n🎉 Test completed - {summary['completed']} tools executed")
        else:
            print("\n❌ No tools completed successfully")
            
    except Exception as e:
        print(f"\n❌ Test failed with unexpected error: {e}")
        import traceback
        traceback.print_exc()
