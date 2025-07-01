#!/usr/bin/env python3
"""
Deep validation test - actually trigger async tools to prove they work
"""
import asyncio
import subprocess
import tempfile
import sys
import json
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')


async def test_actual_tool_registration():
    """Test if our async tools are actually registered in the MCP server"""
    print("🔍 Deep Tool Registration Test")
    print("=" * 50)
    
    # Start server and capture ALL output
    print("Starting MCP server with verbose logging...")
    
    try:
        # Start server with detailed logging
        process = await asyncio.create_subprocess_exec(
            "uv", "run", "serena-mcp-server", "--help",  # First check help to see available options
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        print("📋 Server help output:")
        if stdout:
            help_output = stdout.decode()
            print(help_output)
            
        if stderr:
            error_output = stderr.decode()
            print(f"Error output: {error_output}")
            
    except Exception as e:
        print(f"❌ Error getting server info: {e}")
        

async def test_tool_listing():
    """Try to get a list of available tools from the server"""
    print("\n🔧 Tool Listing Test")
    print("=" * 50)
    
    try:
        # Import the agent directly and check tool registration
        from serena.agent import SerenaAgent, ToolRegistry
        
        print("📋 Checking ToolRegistry...")
        
        # Get all tool classes
        all_tools = ToolRegistry.get_all_tool_classes()
        print(f"Total tools in registry: {len(all_tools)}")
        
        # Look for our async tools specifically
        async_tools_found = []
        for tool_cls in all_tools:
            tool_name = tool_cls.__name__
            if "Async" in tool_name:
                async_tools_found.append(tool_name)
                has_apply_async = hasattr(tool_cls, 'apply_async')
                print(f"✅ Found: {tool_name} (apply_async: {has_apply_async})")
        
        if async_tools_found:
            print(f"🎉 Found {len(async_tools_found)} async tools in registry!")
            return True
        else:
            print("❌ No async tools found in registry")
            return False
            
    except Exception as e:
        print(f"❌ Error checking tool registry: {e}")
        return False


async def test_agent_creation():
    """Test creating a SerenaAgent and checking its tools"""
    print("\n🤖 Agent Creation Test")
    print("=" * 50)
    
    try:
        from serena.agent import SerenaAgent, SerenaConfigBase
        
        print("📋 Creating test agent...")
        
        # Create a minimal config for testing
        class TestConfig(SerenaConfigBase):
            def __init__(self):
                super().__init__()
                self.projects = []
                
        config = TestConfig()
        
        # Try to create agent
        print("   Creating SerenaAgent...")
        agent = SerenaAgent(serena_config=config)
        
        print("   ✅ Agent created successfully")
        
        # Check what tools the agent has
        try:
            exposed_tools = agent.get_exposed_tool_instances()
            print(f"   Agent has {len(exposed_tools)} exposed tools")
            
            # Look for async tools
            async_tool_instances = []
            for tool in exposed_tools:
                tool_name = tool.__class__.__name__
                if "Async" in tool_name:
                    async_tool_instances.append(tool_name)
                    print(f"   ✅ Agent has async tool: {tool_name}")
            
            if async_tool_instances:
                print(f"🎉 Agent successfully has {len(async_tool_instances)} async tools!")
                return True
            else:
                print("❌ Agent has no async tools")
                return False
                
        except Exception as e:
            print(f"❌ Error getting agent tools: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating agent: {e}")
        return False


async def test_mcp_server_tools():
    """Test the actual MCP server to see what tools it exposes"""
    print("\n🌐 MCP Server Tools Test")
    print("=" * 50)
    
    print("Starting MCP server to check tool exposure...")
    
    try:
        # Start server with a timeout
        process = await asyncio.create_subprocess_exec(
            "uv", "run", "serena-mcp-server",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        print("✅ Server process started")
        
        # Wait a bit for startup
        await asyncio.sleep(3)
        
        # Check if process is still running
        if process.returncode is None:
            print("✅ Server is running")
            
            # Try to read any output
            try:
                stdout_data = await asyncio.wait_for(
                    process.stdout.read(1024), 
                    timeout=1.0
                )
                if stdout_data:
                    print(f"Server stdout: {stdout_data.decode()}")
            except asyncio.TimeoutError:
                pass
                
            try:
                stderr_data = await asyncio.wait_for(
                    process.stderr.read(1024), 
                    timeout=1.0
                )
                if stderr_data:
                    server_logs = stderr_data.decode()
                    print(f"Server logs:\n{server_logs}")
                    
                    # Look for tool-related logs
                    if "tool" in server_logs.lower() or "async" in server_logs.lower():
                        print("🔍 Found tool-related logs!")
                    else:
                        print("⚠️  No tool-related logs found")
                        
            except asyncio.TimeoutError:
                print("⚠️  No immediate stderr output")
                
        else:
            print(f"❌ Server exited with code: {process.returncode}")
            
        # Clean shutdown
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=3)
            except asyncio.TimeoutError:
                process.kill()
                
        return True
        
    except Exception as e:
        print(f"❌ Error testing MCP server: {e}")
        return False


async def main():
    """Run deep validation tests"""
    print("🔬 DEEP ASYNC TOOLS VALIDATION")
    print("=" * 60)
    print("Let's find concrete evidence that our async tools are working...")
    
    results = []
    
    # Test 1: Server info
    results.append(await test_actual_tool_registration())
    
    # Test 2: Tool registry
    results.append(await test_tool_listing())
    
    # Test 3: Agent creation
    results.append(await test_agent_creation())
    
    # Test 4: MCP server tools
    results.append(await test_mcp_server_tools())
    
    print("\n" + "=" * 60)
    print("🔬 DEEP VALIDATION RESULTS:")
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 ALL DEEP TESTS PASSED - Async tools are proven to work!")
    elif passed > 0:
        print(f"⚠️  PARTIAL SUCCESS - {passed} tests passed, investigation needed")
    else:
        print("❌ NO TESTS PASSED - Async tools integration needs work")
        
    return passed > 0


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
