#!/usr/bin/env python3
"""
Test runner for async tool silent failure detection.
Runs all the test files in sequence and provides a comprehensive report.
"""
import asyncio
import subprocess
import sys
from pathlib import Path
import time


def run_command(command: str, description: str) -> tuple[bool, str]:
    """Run a command and return success status and output"""
    print(f"\n🚀 {description}")
    print(f"   Running: {command}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        success = result.returncode == 0
        output = result.stdout + result.stderr
        
        if success:
            print(f"   ✅ Completed successfully")
        else:
            print(f"   ❌ Failed with return code {result.returncode}")
        
        return success, output
        
    except subprocess.TimeoutExpired:
        print(f"   ⏰ Timed out after 5 minutes")
        return False, "Command timed out"
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False, str(e)


async def main():
    """Run all async tool tests"""
    print("🧪 Async Tool Silent Failure Test Suite")
    print("=" * 50)
    print(f"Starting at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get the directory containing this script
    script_dir = Path(__file__).parent
    
    # Test files to run
    test_files = [
        ("test_async_silent_failures.py", "Comprehensive Silent Failure Tests"),
        ("test_mcp_integration.py", "Enhanced MCP Integration Tests"),
        ("test_async_failure_simulator.py", "Failure Mode Simulation Tests"),
        ("proposed_async_fixes.py", "Enhanced Error Handling Demo"),
    ]
    
    results = []
    
    for test_file, description in test_files:
        test_path = script_dir / test_file
        
        if not test_path.exists():
            print(f"\n❌ Test file not found: {test_file}")
            results.append((test_file, False, "File not found"))
            continue
        
        # Run the test
        command = f"python {test_path}"
        success, output = run_command(command, description)
        results.append((test_file, success, output))
        
        # Show a preview of the output
        if output:
            lines = output.split('\n')
            preview_lines = [line for line in lines[-20:] if line.strip()]  # Last 20 non-empty lines
            if preview_lines:
                print("   Output preview:")
                for line in preview_lines[:10]:  # Show max 10 lines
                    print(f"     {line}")
                if len(preview_lines) > 10:
                    print(f"     ... ({len(preview_lines) - 10} more lines)")
    
    # Generate summary report
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY REPORT")
    print("=" * 60)
    
    total_tests = len(results)
    successful_tests = sum(1 for _, success, _ in results if success)
    failed_tests = total_tests - successful_tests
    
    print(f"Total tests run: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Success rate: {(successful_tests/total_tests)*100:.1f}%")
    
    print("\nDetailed Results:")
    for test_file, success, output in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} {test_file}")
        
        if not success:
            # Show error details for failed tests
            error_lines = [line for line in output.split('\n') if 'error' in line.lower() or 'exception' in line.lower()]
            if error_lines:
                print(f"    Error: {error_lines[0][:100]}...")
    
    # Check for specific silent failure indicators
    print("\n🔍 SILENT FAILURE ANALYSIS:")
    
    silent_failure_indicators = []
    
    for test_file, success, output in results:
        if "returned None" in output:
            silent_failure_indicators.append(f"{test_file}: Tool returned None")
        if "returned empty" in output:
            silent_failure_indicators.append(f"{test_file}: Tool returned empty")
        if "timed out" in output.lower():
            silent_failure_indicators.append(f"{test_file}: Tool timed out")
        if "POTENTIAL SILENT FAILURE" in output:
            silent_failure_indicators.append(f"{test_file}: Potential silent failure detected")
    
    if silent_failure_indicators:
        print("⚠️  Silent failure indicators found:")
        for indicator in silent_failure_indicators:
            print(f"   - {indicator}")
    else:
        print("✅ No silent failure indicators detected")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    
    if failed_tests > 0:
        print("   - Review failed tests and fix underlying issues")
    
    if silent_failure_indicators:
        print("   - Implement enhanced error handling (see proposed_async_fixes.py)")
        print("   - Add timeout protection to all async tools")
        print("   - Implement monitoring/heartbeat for long-running operations")
        print("   - Add input validation for all tool parameters")
    else:
        print("   - Async tools appear to be handling errors correctly")
        print("   - Continue monitoring in production")
    
    print(f"\nCompleted at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Return appropriate exit code
    return 0 if failed_tests == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
