#!/usr/bin/env python3
"""
Async Tool Failure Simulator - simulate various failure modes for testing
"""
import asyncio
import pytest
import json
import tempfile
from pathlib import Path
import sys
from unittest.mock import Mock, patch

# Add src to path to import our modules
sys.path.insert(0, 'src')


class AsyncToolFailureSimulator:
    """Simulate various failure modes for testing"""
    
    @staticmethod
    async def simulate_instant_return_none():
        """Tool that returns None immediately"""
        return None
        
    @staticmethod
    async def simulate_hang_forever():
        """Tool that hangs indefinitely"""
        await asyncio.sleep(float('inf'))
        
    @staticmethod
    async def simulate_exception_no_return():
        """Tool that raises exception without proper handling"""
        raise RuntimeError("Simulated failure")
        
    @staticmethod
    async def simulate_empty_response():
        """Tool that returns empty string"""
        return ""
    
    @staticmethod
    async def simulate_partial_execution():
        """Tool that starts execution but fails midway"""
        print("Tool started...")
        await asyncio.sleep(0.1)  # Simulate some work
        raise Exception("Simulated mid-execution failure")
    
    @staticmethod
    async def simulate_very_long_execution():
        """Tool that takes a very long time"""
        for i in range(100):
            await asyncio.sleep(0.1)
            print(f"Progress: {i}/100")
        return "Finally completed after long execution"


@pytest.mark.asyncio
async def test_async_tool_failure_modes():
    """Test various failure modes"""
    
    print("🧪 Testing Async Tool Failure Modes")
    print("=" * 40)
    
    # Test 1: None return
    print("\n📍 Test 1: Tool returns None")
    result = await AsyncToolFailureSimulator.simulate_instant_return_none()
    assert result is None
    print("   ✅ Confirmed tool returns None")
    
    # Test 2: Timeout
    print("\n📍 Test 2: Tool hangs indefinitely")
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            AsyncToolFailureSimulator.simulate_hang_forever(),
            timeout=1.0
        )
    print("   ✅ Timeout works correctly")
    
    # Test 3: Exception
    print("\n📍 Test 3: Tool raises exception")
    with pytest.raises(RuntimeError):
        await AsyncToolFailureSimulator.simulate_exception_no_return()
    print("   ✅ Exception raised correctly")
    
    # Test 4: Empty response
    print("\n📍 Test 4: Tool returns empty string")
    result = await AsyncToolFailureSimulator.simulate_empty_response()
    assert result == ""
    print("   ✅ Confirmed tool returns empty string")
    
    # Test 5: Partial execution failure
    print("\n📍 Test 5: Tool fails during execution")
    with pytest.raises(Exception):
        await AsyncToolFailureSimulator.simulate_partial_execution()
    print("   ✅ Mid-execution failure handled")


async def test_tool_monitoring_detection():
    """Test that our monitoring can detect various failure patterns"""
    
    print("\n🔍 Testing Monitoring Detection")
    print("=" * 35)
    
    class MockSession:
        """Mock MCP session for testing"""
        
        def __init__(self, simulator_func):
            self.simulator_func = simulator_func
            
        async def call_tool(self, tool_name, **kwargs):
            """Simulate calling a tool"""
            return await self.simulator_func()
    
    # Import the monitor from our main test file
    from test_mcp_integration import ToolCallMonitor
    
    monitor = ToolCallMonitor()
    
    # Test monitoring None return
    print("\n📍 Monitoring Test 1: None return detection")
    session = MockSession(AsyncToolFailureSimulator.simulate_instant_return_none)
    result = await monitor.monitored_call_tool(session, "test_tool", timeout=5.0)
    assert result is None
    print("   ✅ Monitor detected None return")
    
    # Test monitoring empty return
    print("\n📍 Monitoring Test 2: Empty return detection")
    session = MockSession(AsyncToolFailureSimulator.simulate_empty_response)
    result = await monitor.monitored_call_tool(session, "test_tool", timeout=5.0)
    assert result == ""
    print("   ✅ Monitor detected empty return")
    
    # Test monitoring timeout
    print("\n📍 Monitoring Test 3: Timeout detection")
    session = MockSession(AsyncToolFailureSimulator.simulate_hang_forever)
    try:
        result = await monitor.monitored_call_tool(session, "test_tool", timeout=1.0)
        assert False, "Should have timed out"
    except asyncio.TimeoutError:
        print("   ✅ Monitor detected timeout")
    
    # Test monitoring exception
    print("\n📍 Monitoring Test 4: Exception detection")
    session = MockSession(AsyncToolFailureSimulator.simulate_exception_no_return)
    try:
        result = await monitor.monitored_call_tool(session, "test_tool", timeout=5.0)
        assert False, "Should have raised exception"
    except RuntimeError:
        print("   ✅ Monitor detected exception")
    
    # Check summary
    summary = monitor.get_summary()
    print(f"\n📊 Monitor Summary:")
    print(f"   Total calls: {summary['total_calls']}")
    print(f"   Warnings: {summary['warnings']}")
    for status, count in summary['by_status'].items():
        print(f"   {status}: {count}")


def test_real_tool_validation():
    """Test real Serena tools if available"""
    
    print("\n🔧 Testing Real Serena Tools")
    print("=" * 30)
    
    try:
        from serena.agent import SerenaAgent
        from serena.agent import AsyncReadFileTool, AsyncCreateTextFileTool, AsyncExecuteShellCommandTool
        
        # Test with real tools
        async def run_real_tool_tests():
            with tempfile.TemporaryDirectory() as temp_dir:
                project_root = Path(temp_dir)
                
                # Create minimal agent
                agent = SerenaAgent(project_root=str(project_root), logs_dir=None)
                
                # Test cases that might cause silent failures
                test_cases = [
                    (AsyncReadFileTool, {"relative_path": ""}, "Empty path"),
                    (AsyncReadFileTool, {"relative_path": None}, "None path"),
                    (AsyncCreateTextFileTool, {"relative_path": "test.txt", "content": None}, "None content"),
                    (AsyncCreateTextFileTool, {"relative_path": "", "content": "test"}, "Empty filename"),
                    (AsyncExecuteShellCommandTool, {"command": ""}, "Empty command"),
                    (AsyncExecuteShellCommandTool, {"command": None}, "None command"),
                ]
                
                for tool_class, kwargs, description in test_cases:
                    print(f"\n🔧 Testing {tool_class.__name__}: {description}")
                    try:
                        tool = tool_class(agent)
                        result = await asyncio.wait_for(
                            tool.apply_async(**kwargs),
                            timeout=10.0
                        )
                        
                        print(f"   Result type: {type(result)}")
                        if result is None:
                            print("   ❌ WARNING: Tool returned None!")
                        elif result == "":
                            print("   ❌ WARNING: Tool returned empty string!")
                        else:
                            print(f"   ✅ Tool returned: {str(result)[:100]}...")
                            
                    except Exception as e:
                        print(f"   ❌ Exception: {type(e).__name__}: {e}")
        
        # Run the async test
        asyncio.run(run_real_tool_tests())
        
    except ImportError as e:
        print(f"   ❌ Could not import Serena tools: {e}")
        print("   This test requires Serena to be properly installed")


if __name__ == "__main__":
    # Run pytest-style tests
    print("🚀 Running Async Tool Failure Simulator Tests")
    print("=" * 50)
    
    # Run simulation tests
    asyncio.run(test_async_tool_failure_modes())
    
    # Run monitoring tests
    asyncio.run(test_tool_monitoring_detection())
    
    # Run real tool tests
    test_real_tool_validation()
    
    print("\n🎉 All failure simulation tests completed!")
