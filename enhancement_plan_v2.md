# Enhanced Observability and Responsiveness Plan for Serena MCP Server

## 1. Introduction

This document outlines a revised and more detailed plan for enhancing the Serena MCP server's observability and responsiveness. It builds upon the initial ideas and implemented changes, and adopts the more robust strategy detailed in `AschyncPlan.md` to address the core issue of the server appearing frozen during long-running tool calls.

## 2. Implemented Enhancements & Critique

The following foundational enhancements have been implemented in `src/serena/mcp.py`:

*   **Port Logging:** The server now logs the host and port it is listening on at startup, providing clear confirmation that the server has started successfully.
*   **Basic Heartbeat Logging:** A background thread now logs a "Serena MCP server is alive..." message every 60 seconds.

**Critique:** While these are good first steps, the analysis in `AschyncPlan.md` revealed a critical flaw in the heartbeat implementation. Because the SerenaAgent executes tool calls synchronously in a single worker process, a long-running tool will block the entire process. This will starve the heartbeat thread, preventing it from running. The server will still appear frozen precisely when feedback is most needed.

This realization makes it clear that a simple heartbeat is insufficient. To solve the core problem, the tools themselves must be made non-blocking.

## 3. Proposed Enhancements: Asynchronous Tools and Progress Reporting

This plan replaces the previous proposal of a task queue and polling API with a more integrated approach focused on modifying the tools directly.

### 3.1. Convert I/O-Bound Tools to `async`

The primary cause of the server freezing is synchronous, blocking I/O operations. The most effective solution is to convert these operations to be asynchronous.

*   **Strategy:** Identify tools whose execution time is dominated by waiting for network or disk I/O. Convert their synchronous `def` methods to `async def` and use `await` for the I/O operations. This will allow the server's event loop to remain responsive.
*   **Key Candidates for Conversion:**
    *   `read_file` / `write_file`: Pure disk I/O. Can be converted using a library like `aiofiles`.
    *   `run_shell_command`: Can be made non-blocking by using `asyncio.create_subprocess_shell`.
    *   `get_symbols_in_file`: LSP communication is I/O-bound (inter-process communication) and is a prime candidate for being converted to `async`.
    *   `initialize_workspace`: This is the most critical tool. It should be refactored into an `async` orchestrator that `await`s other smaller, asynchronous operations.

### 3.2. Implement a Progress Callback System

For complex, multi-stage tools, simply making them `async` is not enough to provide visibility. A progress callback system is needed for real-time feedback.

*   **Strategy:**
    1.  Define a `progress_callback` function parameter in the `SerenaAgent`'s tool execution method.
    2.  This callback will be passed down to the tools when they are invoked.
    3.  Modify the internal logic of complex tools like `initialize_workspace` to call the callback at key milestones (e.g., `progress_callback("Scanning files...")`, `progress_callback("Starting language server...")`).
*   **Benefit:** The user will see a stream of status updates in the log viewer and GUI, providing a clear indication of what the server is doing and confirming that it has not frozen.

## 4. Critique of the Dynamic Port Wrapper Script

The dynamic port wrapper script, as proposed in the original `Enhancementplan.md`, remains a non-viable solution. IDE clients expect to connect to a fixed, predictable port and do not have a mechanism to discover a dynamically assigned one. Therefore, we will continue to use a fixed port for the Serena MCP server.

## 5. Roadmap

We propose the following phased roadmap:

1.  **Phase 1: Convert High-Impact Tools to `async`**. Begin by converting the most straightforward I/O-bound tools (`read_file`, `run_shell_command`) to `async` to achieve initial responsiveness gains.
2.  **Phase 2: Implement the Progress Callback System**. Introduce the `progress_callback` mechanism to provide the infrastructure for detailed status updates.
3.  **Phase 3: Refactor Complex Tools**. Incrementally refactor `initialize_workspace` and other complex tools to be fully asynchronous and utilize the progress callback system to report their status.

---

## 6. Automated Test Plan

This plan uses a testing framework like `pytest` and `pytest-asyncio` and assumes the ability to interact with and inspect the state of the Serena agent and its logs.

### **Objective** To verify that the enhancements to the Serena MCP server correctly implement non-blocking tool calls, provide progress feedback, and maintain core functionality.

### **Test Suite 1: Foundational Observability**

#### **Test Case 1.1: Verify Server Startup and Port Logging**

* **Goal:** Ensure the server logs the correct listening port upon startup.
* **Procedure:**
    1.  Start the Serena server.
    2.  Scan the initial log output.
    3.  **Assert** that a log message matching `Serena Dashboard started on port [port_number]` exists.

#### **Test Case 1.2: Verify Idle-Time Heartbeat**

* **Goal:** Confirm the non-blocking heartbeat logs messages periodically when the server is idle.
* **Procedure:**
    1.  Start the server and leave it idle.
    2.  Monitor the logs for a period of ~70 seconds.
    3.  **Assert** that the "still alive" heartbeat message appears at least once.
    4.  **Assert** that subsequent calls to simple, fast tools succeed immediately, proving the heartbeat is not blocking.

---

### **Test Suite 2: Asynchronous Tool Execution**

#### **Test Case 2.1: Verify Non-Blocking I/O Tools (`read_file`/`write_file`)**

* **Goal:** Confirm that I/O-bound file operations do not block the agent.
* **Procedure:**
    1.  Create a large temporary file.
    2.  Initiate an async `read_file` call on the large file.
    3.  Immediately after, initiate a fast operation (e.g., a simple calculation or another tool call).
    4.  **Assert** that the second operation completes *before* the `read_file` operation finishes, proving non-blocking execution.

#### **Test Case 2.2: Verify Non-Blocking Shell Command (`run_shell_command`)**

* **Goal:** Ensure that long-running external commands do not freeze the agent.
* **Procedure:**
    1.  Execute `run_shell_command` with a command that has a significant delay (e.g., `sleep 3`).
    2.  Immediately initiate another tool call.
    3.  **Assert** that the second tool call executes and returns while the `sleep` command is still running.

---

### **Test Suite 3: Progress and Final State**

#### **Test Case 3.1: Verify Progress Callback System**

* **Goal:** Validate that complex tools provide real-time progress updates. This is the most critical test.
* **Procedure:**
    1.  Design the test to "mock" the progress callback function, allowing it to capture all messages sent to it.
    2.  Trigger the `initialize_workspace` tool, passing the mocked callback.
    3.  As the tool runs, collect all messages received by the callback into a list.
    4.  **Assert** that the list of captured messages is not empty.
    5.  **Assert** that the list contains specific, expected milestone messages (e.g., "Scanning files...", "Starting language server...").

#### **Test Case 3.2: Verify Tool Output Correctness**

* **Goal:** Ensure that the refactored asynchronous tools still produce accurate results.
* **Procedure:**
    1.  **`get_file_tree`**: Run on a small, predefined directory structure and **assert** that the returned JSON or object representation is exactly as expected.
    2.  **`get_symbols_in_file`**: Run on a source file with known symbols (functions, classes) and **assert** that the list of returned symbols is correct.
    3.  **`run_shell_command`**: Execute a simple command like `echo "hello"` and **assert** that the tool's return value contains "hello".
