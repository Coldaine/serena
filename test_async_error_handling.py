#!/usr/bin/env python3
"""
Test script to verify that the async error handling fixes work correctly.
"""
import asyncio
import json
import tempfile
import os
from pathlib import Path
import sys

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from serena.agent import AsyncFindFileTool, AsyncListDirTool, AsyncReadFileTool


class MockAgent:
    """Mock agent for testing"""
    def __init__(self, project_root):
        self.project_root = project_root
    
    def validate_relative_path(self, path):
        """Mock validation - just pass through"""
        pass
    
    def path_is_gitignored(self, path):
        """Mock gitignore check - always return False"""
        return False


class MockAsyncTool:
    """Base mock for async tools"""
    def __init__(self, project_root):
        self.agent = MockAgent(project_root)
    
    def get_project_root(self):
        return self.agent.project_root
    
    def _limit_length(self, text, max_length):
        """Mock limit length"""
        return text


async def test_async_find_file_error_handling():
    """Test that AsyncFindFileTool handles missing directories gracefully"""
    print("Testing AsyncFindFileTool error handling")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mock tool
        tool = AsyncFindFileTool(None)
        tool.agent = MockAgent(temp_dir)
        tool.get_project_root = lambda: temp_dir
        
        # Test with non-existent directory
        result = await tool.apply_async(
            file_mask="*.txt",
            relative_path="non_existent_dir",
            progress_callback=lambda msg: print(f"    Progress: {msg}")
        )
        
        # Parse result
        result_data = json.loads(result)
        
        # Check that it returns an error instead of crashing
        if "error" in result_data:
            print("    OK Successfully handled missing directory error")
            print(f"    OK Error message: {result_data['error']}")
            return True
        else:
            print("    OK Did not return error for missing directory")
            return False


async def test_async_list_dir_error_handling():
    """Test that AsyncListDirTool handles missing directories gracefully"""
    print("Testing AsyncListDirTool error handling")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mock tool
        tool = AsyncListDirTool(None)
        tool.agent = MockAgent(temp_dir)
        tool.get_project_root = lambda: temp_dir
        tool._limit_length = lambda text, max_len: text
        
        # Test with non-existent directory
        result = await tool.apply_async(
            relative_path="non_existent_dir",
            recursive=True,
            progress_callback=lambda msg: print(f"    Progress: {msg}")
        )
        
        # Parse result
        result_data = json.loads(result)
        
        # Check that it returns an error instead of crashing
        if "error" in result_data:
            print("    OK Successfully handled missing directory error")
            print(f"    OK Error message: {result_data['error']}")
            return True
        else:
            print("    OK Did not return error for missing directory")
            return False


async def test_async_read_file_error_handling():
    """Test that AsyncReadFileTool handles missing files gracefully"""
    print("Testing AsyncReadFileTool error handling")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mock tool
        tool = AsyncReadFileTool(None)
        tool.agent = MockAgent(temp_dir)
        tool.get_project_root = lambda: temp_dir
        tool._limit_length = lambda text, max_len: text
        tool.lines_read = type('', (), {'add_lines_read': lambda *args: None})()
        
        # Test with non-existent file
        result = await tool.apply_async(
            relative_path="non_existent_file.txt",
            progress_callback=lambda msg: print(f"    Progress: {msg}")
        )
        
        # Check that it returns an error instead of crashing
        if result.startswith("Error:"):
            print("    OK Successfully handled missing file error")
            print(f"    OK Error message: {result}")
            return True
        else:
            print("    OK Did not return error for missing file")
            return False


async def main():
    """Run all tests"""
    print("Testing Async Tool Error Handling")
    print("=" * 50)
    
    tests = [
        test_async_find_file_error_handling,
        test_async_list_dir_error_handling,
        test_async_read_file_error_handling
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
            print()
        except Exception as e:
            print(f"    OK Test failed with exception: {e}")
            results.append(False)
            print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("=" * 50)
    print(f"OK Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("OK All tests passed! Async error handling is working correctly.")
        return True
    else:
        print("OK  Some tests failed. Error handling needs more work.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)