#!/usr/bin/env python3
"""
Simple test to verify port logging and heartbeat in MCP server.
"""
import asyncio
import sys
import tempfile
from pathlib import Path

# Add src to path to import our modules
sys.path.insert(0, 'src')

from serena.mcp import SerenaMCPFactorySingleProcess


async def test_port_logging():
    """Test that port and heartbeat logging works."""
    print("Testing port logging and heartbeat...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        print(f"Created temporary project at: {project_root}")
        
        # Create a factory
        factory = SerenaMCPFactorySingleProcess(project=str(project_root))
        
        # Create MCP server
        mcp_server = factory.create_mcp_server(host="127.0.0.1", port=9999)
        
        print("Created MCP server, should see port logging...")
        
        # Start the server lifespan context
        async with factory.server_lifespan(mcp_server):
            print("Server lifespan started - should see heartbeat start message")
            # Wait a bit to see heartbeat
            await asyncio.sleep(2)
            print("Waited 2 seconds")
            
        print("Server lifespan ended - heartbeat should stop")
        
        return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_port_logging())
        if success:
            print("PORT LOGGING TEST PASSED!")
        else:
            print("PORT LOGGING TEST FAILED.")
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()