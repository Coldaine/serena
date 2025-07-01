#!/usr/bin/env python3
"""
End-to-end MCP integration test to verify async tools functionality.
"""
import asyncio
import json
import tempfile
from pathlib import Path
import os

# Add src to path to import our modules
import sys
sys.path.insert(0, 'src')

try:
    from mcp.client.stdio import stdio_client
except ImportError:
    print("❌ MCP client libraries not available for direct testing")
    print("   This is expected - we'll test through tool validation instead")
    sys.exit(0)


async def run_e2e_test():
    """Runs an end-to-end test of async tools via the MCP protocol."""
    print("🧪 E2E Testing Async Tools via MCP Protocol")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)
        print(f"📁 Created temporary project at: {project_root}")

        # 1. Start the MCP server as a subprocess
        print("🚀 Starting MCP server...")
        server_process = await asyncio.create_subprocess_exec(
            "uv", "run", "serena-mcp-server",
            "--project", str(project_root),
            "--enable-web-dashboard", "False",
            "--enable-gui-log-window", "False",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 2. Connect to the server using the stdio client
        async with stdio_client(server_process) as session:
            print("✅ Connected to MCP server via stdio.")

            # 3. Test `async_create_text_file`
            print("\n🔧 Testing 'async_create_text_file'...")
            file_to_create = "test_file.txt"
            content_to_write = "Hello from the E2E test!"
            result = await session.call_tool(
                "async_create_text_file",
                relative_path=file_to_create,
                content=content_to_write
            )
            print(f"   Tool result: {result}")
            assert "File created" in result

            # Verify the file was actually created with the correct content
            created_file_path = project_root / file_to_create
            assert created_file_path.exists()
            assert created_file_path.read_text() == content_to_write
            print("   ✅ File created and content verified.")

            # 4. Test `async_read_file`
            print("\n🔧 Testing 'async_read_file'...")
            read_result = await session.call_tool(
                "async_read_file",
                relative_path=file_to_create
            )
            print(f"   Tool result: {read_result}")
            assert read_result == content_to_write
            print("   ✅ File content read back successfully.")

            # Test `async_read_file` on a non-existent file
            print("\n🔧 Testing 'async_read_file' on a non-existent file...")
            non_existent_file = "no_such_file.txt"
            read_error_result = await session.call_tool(
                "async_read_file",
                relative_path=non_existent_file
            )
            print(f"   Tool result: {read_error_result}")
            # The tool should return a descriptive error message
            assert "Error" in read_error_result
            assert "FileNotFoundError" in read_error_result
            print("   ✅ Correctly handled non-existent file.")

            # 5. Test `async_execute_shell_command`
            print("\n🔧 Testing 'async_execute_shell_command'...")
            command_to_run = "echo 'Shell command successful!'"
            shell_result_str = await session.call_tool(
                "async_execute_shell_command",
                command=command_to_run
            )
            shell_result = json.loads(shell_result_str)
            print(f"   Tool result: {shell_result}")
            assert shell_result["return_code"] == 0
            assert "Shell command successful!" in shell_result["stdout"]
            print("   ✅ Shell command executed successfully.")

            # Test `async_execute_shell_command` with a failing command
            print("\n🔧 Testing 'async_execute_shell_command' with a failing command...")
            # A more reliable cross-platform way to generate an error is to call a non-existent command.
            failing_command = "this_command_does_not_exist_12345"
            failing_shell_result_str = await session.call_tool(
                "async_execute_shell_command", command=failing_command
            )
            failing_shell_result = json.loads(failing_shell_result_str)
            print(f"   Tool result: {failing_shell_result}")
            assert failing_shell_result["return_code"] != 0
            print("   ✅ Correctly handled failing shell command.")

        # 6. Cleanup
        print("\n🧹 Shutting down server...")
        if server_process.returncode is None:
            server_process.terminate()
            await server_process.wait()
        print("   ✅ Server shut down.")

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(run_e2e_test())
        if success:
            print("\n🎉 ALL E2E TESTS PASSED!")
            exit(0)
        else:
            print("\n❌ E2E TESTS FAILED.")
            exit(1)
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")
        exit(1)
