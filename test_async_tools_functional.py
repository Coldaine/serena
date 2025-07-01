#!/usr/bin/env python3
"""
Simple test script to verify async tools functionality without full agent setup
"""
import asyncio
import tempfile
import os
from pathlib import Path

# Add src to path to import our modules
import sys
sys.path.insert(0, 'src')

import aiofiles


async def test_aiofiles_directly():
    """Test aiofiles functionality directly"""
    print("\n=== Testing aiofiles directly ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = Path(temp_dir) / "test_aiofiles.txt"
        test_content = "Hello from aiofiles!\nThis is a test file.\nLine 3 content."
        
        # Test async file write
        print("1. Testing async file write...")
        async with aiofiles.open(test_file, 'w') as f:
            await f.write(test_content)
        print("   ✅ Async write completed")
        
        # Test async file read
        print("2. Testing async file read...")
        async with aiofiles.open(test_file, 'r') as f:
            content = await f.read()
        print(f"   ✅ Async read completed, length: {len(content)} characters")
        
        # Verify content matches
        assert content == test_content, "File content should match"
        print("   ✅ Content verification passed")
        
        return True


async def test_asyncio_subprocess():
    """Test asyncio subprocess functionality"""
    print("\n=== Testing asyncio subprocess ===")
    
    # Use a simple cross-platform command
    if os.name == 'nt':  # Windows
        cmd_args = ['cmd', '/c', 'echo Hello from async subprocess']
    else:  # Unix-like
        cmd_args = ['echo', 'Hello from async subprocess']
    
    print(f"1. Testing async subprocess: {' '.join(cmd_args)}")
    
    # Create subprocess
    process = await asyncio.create_subprocess_exec(
        *cmd_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Wait for completion and get output
    stdout, stderr = await process.communicate()
    
    print(f"   Return code: {process.returncode}")
    print(f"   Stdout: {stdout.decode().strip()}")
    if stderr:
        print(f"   Stderr: {stderr.decode().strip()}")
    
    # Verify subprocess worked
    assert process.returncode == 0, "Subprocess should exit successfully"
    assert "Hello from async subprocess" in stdout.decode(), "Output should contain our test message"
    
    print("   ✅ Async subprocess test passed")
    return True


async def test_progress_callback_simulation():
    """Test progress callback simulation"""
    print("\n=== Testing Progress Callback Simulation ===")
    
    progress_messages = []
    
    async def mock_progress_callback(message: str):
        """Mock progress callback that collects messages"""
        progress_messages.append(message)
        print(f"   [PROGRESS] {message}")
    
    # Simulate some async work with progress updates
    print("1. Simulating async work with progress callbacks...")
    
    await mock_progress_callback("Starting operation...")
    await asyncio.sleep(0.1)  # Simulate some work
    
    await mock_progress_callback("Processing data...")
    await asyncio.sleep(0.1)  # Simulate more work
    
    await mock_progress_callback("Finalizing...")
    await asyncio.sleep(0.1)  # Simulate final work
    
    await mock_progress_callback("Operation completed")
    
    # Verify we collected progress messages
    assert len(progress_messages) == 4, "Should have collected 4 progress messages"
    assert "Starting operation..." in progress_messages[0], "First message should be start"
    assert "Operation completed" in progress_messages[-1], "Last message should be completion"
    
    print("   ✅ Progress callback simulation passed")
    return True


async def main():
    """Run all basic async functionality tests"""
    print("🧪 Starting Basic Async Functionality Tests")
    print("=" * 50)
    
    try:
        # Test aiofiles directly
        await test_aiofiles_directly()
        
        # Test asyncio subprocess
        await test_asyncio_subprocess()
        
        # Test progress callback pattern
        await test_progress_callback_simulation()
        
        print("\n" + "=" * 50)
        print("🎉 ALL BASIC ASYNC TESTS PASSED!")
        print("✅ aiofiles: Working")
        print("✅ asyncio subprocess: Working")
        print("✅ Progress callback pattern: Working")
        print("✅ Python async/await: Working")
        
        print("\n📋 Next Step: Test async tools integration with agent")
        print("   The core async functionality is confirmed working.")
        print("   Our async tools should work when properly integrated.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run the async tests
    success = asyncio.run(main())
    exit(0 if success else 1)
