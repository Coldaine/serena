#!/usr/bin/env python3
"""
Live Serena log reader - simpler approach to monitor logs
"""
import asyncio
import subprocess
import sys
import time
from datetime import datetime

async def monitor_serena_logs():
    """Monitor Serena MCP server logs in real-time"""
    print("🔍 Live Serena Log Monitor")
    print("=" * 50)
    print("Starting Serena MCP server with live log capture...")
    
    try:
        # Start server with both stdout and stderr captured
        process = await asyncio.create_subprocess_exec(
            "uv", "run", "serena-mcp-server",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,  # Redirect stderr to stdout
            limit=1024*1024  # 1MB buffer
        )
        
        print("✅ Server process started")
        print("📡 Monitoring logs (Press Ctrl+C to stop)...")
        print("-" * 50)
        
        # Monitor logs in real-time
        log_count = 0
        while True:
            # Read line from stdout/stderr
            line = await process.stdout.readline()
            
            if not line:
                # Check if process ended
                if process.returncode is not None:
                    print(f"\n⚠️  Server process ended with code: {process.returncode}")
                    break
                # Wait a bit and continue
                await asyncio.sleep(0.1)
                continue
                
            # Decode and display log
            log_entry = line.decode('utf-8', errors='ignore').strip()
            if log_entry:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"[{timestamp}] {log_entry}")
                log_count += 1
                
                # Show progress callback related logs with highlighting
                if any(keyword in log_entry.lower() for keyword in ['progress', 'async', 'callback', 'tool']):
                    print(f"   🔥 ASYNC/PROGRESS LOG: {log_entry}")
                
    except KeyboardInterrupt:
        print(f"\n⚠️  Monitoring stopped by user (captured {log_count} logs)")
    except Exception as e:
        print(f"\n❌ Error monitoring logs: {e}")
    finally:
        # Clean shutdown
        if 'process' in locals():
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        print("\n✅ Cleanup completed")


async def test_async_tools_with_logs():
    """Test async tools while monitoring logs"""
    print("🧪 Testing Async Tools with Live Log Monitoring")
    print("=" * 60)
    
    # Import our async tools
    sys.path.insert(0, 'src')
    try:
        from serena.agent import (
            AsyncReadFileTool,
            AsyncCreateTextFileTool, 
            AsyncExecuteShellCommandTool
        )
        print("✅ Async tools imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import async tools: {e}")
        return
    
    print("\n📋 Available async tools:")
    async_tools = [AsyncReadFileTool, AsyncCreateTextFileTool, AsyncExecuteShellCommandTool]
    for tool_class in async_tools:
        method_check = "✅" if hasattr(tool_class, 'apply_async') else "❌"
        print(f"   {method_check} {tool_class.__name__}")
    
    print("\n🚀 Starting server with log monitoring...")
    
    # Start monitoring
    await monitor_serena_logs()


if __name__ == "__main__":
    try:
        asyncio.run(test_async_tools_with_logs())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
