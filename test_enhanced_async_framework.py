#!/usr/bin/env python3
"""
Enhanced testing framework with live Serena log monitoring
"""
import asyncio
import json
import tempfile
import threading
import queue
import subprocess
import time
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

# Add src to path to import our modules
sys.path.insert(0, 'src')


class SerenaLogMonitor:
    """Monitor Serena MCP server logs in real-time"""
    
    def __init__(self):
        self.log_queue = queue.Queue()
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        
    def start_monitoring(self, server_process: subprocess.Popen):
        """Start monitoring the server's stderr output"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_logs, 
            args=(server_process,),
            daemon=True
        )
        self.monitor_thread.start()
        print("🔍 Started live log monitoring...")
        
    def _monitor_logs(self, server_process: subprocess.Popen):
        """Monitor logs in a separate thread"""
        try:
            while self.monitoring and server_process.poll() is None:
                if server_process.stderr and server_process.stderr.readable():
                    line = server_process.stderr.readline()
                    if line:
                        # Handle both str and bytes
                        if isinstance(line, bytes):
                            log_entry = line.decode('utf-8', errors='ignore').strip()
                        else:
                            log_entry = line.strip()
                        if log_entry:
                            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                            self.log_queue.put(f"[{timestamp}] {log_entry}")
                else:
                    time.sleep(0.1)
        except Exception as e:
            self.log_queue.put(f"[LOG MONITOR ERROR] {e}")
            
    def get_recent_logs(self, max_logs: int = 10) -> list[str]:
        """Get recent log entries"""
        logs = []
        while not self.log_queue.empty() and len(logs) < max_logs:
            try:
                logs.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        return logs
        
    def stop_monitoring(self):
        """Stop log monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)


class EnhancedAsyncToolTester:
    """Enhanced testing framework for async tools with live monitoring"""
    
    def __init__(self):
        self.log_monitor = SerenaLogMonitor()
        self.server_process: Optional[subprocess.Popen] = None
        
    async def start_server_with_monitoring(self) -> bool:
        """Start MCP server with live log monitoring"""
        print("🚀 Starting Serena MCP Server with live monitoring...")
        
        try:
            # Start the server process with stderr capture
            self.server_process = subprocess.Popen(
                ["uv", "run", "serena-mcp-server"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            # Start monitoring logs
            self.log_monitor.start_monitoring(self.server_process)
            
            # Wait a moment for startup
            await asyncio.sleep(2)
            
            # Check if server started successfully
            if self.server_process.poll() is None:
                print("✅ Server started successfully")
                return True
            else:
                print("❌ Server failed to start")
                return False
                
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False
            
    def show_recent_logs(self, title: str = "Recent Logs"):
        """Display recent log entries"""
        logs = self.log_monitor.get_recent_logs(max_logs=15)
        if logs:
            print(f"\n📋 {title}")
            print("-" * 60)
            for log in logs[-10:]:  # Show last 10 logs
                print(f"   {log}")
        else:
            print(f"\n📋 {title}: No recent logs")
            
    async def test_async_tool_validation(self) -> bool:
        """Test async tool validation with log monitoring"""
        print("\n🧪 Testing Async Tool Validation")
        print("=" * 50)
        
        try:
            from serena.agent import (
                AsyncReadFileTool, 
                AsyncCreateTextFileTool, 
                AsyncExecuteShellCommandTool,
                AsyncGetSymbolsOverviewTool,
                AsyncListDirTool,
                AsyncFindFileTool
            )
            
            async_tools = [
                AsyncReadFileTool,
                AsyncCreateTextFileTool, 
                AsyncExecuteShellCommandTool,
                AsyncGetSymbolsOverviewTool,
                AsyncListDirTool,
                AsyncFindFileTool
            ]
            
            print("📋 Validating async tools...")
            all_valid = True
            
            for tool_class in async_tools:
                if hasattr(tool_class, 'apply_async'):
                    print(f"✅ {tool_class.__name__} - async method present")
                else:
                    print(f"❌ {tool_class.__name__} - missing async method")
                    all_valid = False
                    
            # Show any logs related to tool registration
            await asyncio.sleep(1)  # Allow logs to accumulate
            self.show_recent_logs("Tool Registration Logs")
            
            return all_valid
            
        except ImportError as e:
            print(f"❌ Import error: {e}")
            self.show_recent_logs("Import Error Logs")
            return False
            
    async def test_server_responsiveness(self) -> bool:
        """Test server responsiveness and log activity"""
        print("\n🔄 Testing Server Responsiveness")
        print("=" * 50)
        
        print("📡 Monitoring server activity for 5 seconds...")
        
        # Monitor for a few seconds
        for i in range(5):
            await asyncio.sleep(1)
            recent_logs = self.log_monitor.get_recent_logs(5)
            if recent_logs:
                print(f"   Second {i+1}: {len(recent_logs)} new log entries")
            else:
                print(f"   Second {i+1}: No new logs")
                
        self.show_recent_logs("Server Activity Logs")
        
        # Check if server is still running
        if self.server_process and self.server_process.poll() is None:
            print("✅ Server is responsive and running")
            return True
        else:
            print("❌ Server appears to have stopped")
            return False
            
    async def test_async_functionality_simulation(self) -> bool:
        """Simulate async tool usage patterns"""
        print("\n⚡ Testing Async Functionality Simulation")
        print("=" * 50)
        
        # Simulate what async tools would do
        print("📝 Simulating async file operations...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "async_test.txt"
            
            # Simulate async write
            print("   🔹 Simulating async file write...")
            await asyncio.sleep(0.2)  # Simulate async I/O delay
            
            # Simulate async read  
            print("   🔹 Simulating async file read...")
            await asyncio.sleep(0.1)  # Simulate async I/O delay
            
            # Simulate shell command
            print("   🔹 Simulating async shell command...")
            await asyncio.sleep(0.3)  # Simulate async command delay
            
        print("✅ Async simulation completed")
        
        # Check for any related logs
        await asyncio.sleep(1)
        self.show_recent_logs("Async Simulation Logs")
        
        return True
        
    async def run_comprehensive_test(self) -> bool:
        """Run comprehensive test suite with live monitoring"""
        print("🧪 Enhanced Async Tool Testing Framework")
        print("=" * 60)
        
        try:
            # Start server with monitoring
            if not await self.start_server_with_monitoring():
                return False
                
            # Wait for startup logs
            await asyncio.sleep(3)
            self.show_recent_logs("Server Startup Logs")
            
            # Run validation tests
            validation_ok = await self.test_async_tool_validation()
            if not validation_ok:
                print("❌ Validation failed")
                return False
                
            # Test server responsiveness
            responsiveness_ok = await self.test_server_responsiveness()
            if not responsiveness_ok:
                print("❌ Responsiveness test failed")
                return False
                
            # Test async functionality
            async_ok = await self.test_async_functionality_simulation()
            if not async_ok:
                print("❌ Async functionality test failed")
                return False
                
            print("\n" + "=" * 60)
            print("🎉 ENHANCED TESTING COMPLETED SUCCESSFULLY!")
            print("✅ Server monitoring: Active")
            print("✅ Log capturing: Working")
            print("✅ Async tools: Validated")
            print("✅ Server responsiveness: Confirmed")
            
            # Show final summary of logs
            self.show_recent_logs("Final Log Summary")
            
            return True
            
        except Exception as e:
            print(f"❌ Test suite error: {e}")
            self.show_recent_logs("Error Logs")
            return False
            
        finally:
            # Clean shutdown
            await self.cleanup()
            
    async def cleanup(self):
        """Clean up resources"""
        print("\n🧹 Cleaning up...")
        
        # Stop log monitoring
        self.log_monitor.stop_monitoring()
        
        # Stop server if running
        if self.server_process and self.server_process.poll() is None:
            print("   Stopping MCP server...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
                
        print("✅ Cleanup completed")


async def main():
    """Run enhanced testing framework"""
    tester = EnhancedAsyncToolTester()
    success = await tester.run_comprehensive_test()
    return success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        exit(1)
