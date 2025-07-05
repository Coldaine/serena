# **Architecting for Concurrency: A Definitive Guide to Integrating Synchronous and Asynchronous Tools in a FastMCP Server**

## **Introduction: Unlocking True Concurrency in MCP Servers**

### **1.1 The Promise of the Model Context Protocol (MCP)**

The Model Context Protocol (MCP) represents a foundational shift in how artificial intelligence systems interact with the world. Introduced as an open standard, it provides a universal, standardized framework for creating seamless, bidirectional connections between Large Language Models (LLMs) and external tools, data sources, and systems. Its core purpose is to dismantle the integration silos that have traditionally hindered AI development, offering what is often described as a "USB-C port for AI"—a single, reliable interface for connecting models to the vast ecosystem of digital capabilities. The power of MCP lies in its ability to facilitate complex, agentic workflows where an LLM can move beyond simple text generation to actively execute functions, query databases, read files, and interact with APIs in a secure and structured manner.  
This protocol was fundamentally designed to support the dynamic and often long-running nature of these interactions. The MCP specification and the ecosystem of tools built around it, including various language implementations, inherently support asynchronous and streaming communication patterns. These patterns are not merely optional features; they are critical for building the responsive, high-performance, and real-time AI applications that modern use cases demand. An MCP server that can handle I/O-bound tasks without blocking, stream progress updates to a waiting client, and manage multiple concurrent operations is one that fully realizes the protocol's potential. Therefore, any architectural approach must align with this core design philosophy of asynchronicity and concurrency.

### **1.2 The Architectural Challenge: Bridging Synchronous and Asynchronous Worlds**

This report addresses a critical architectural flaw identified in a Model Context Protocol (MCP) server implementation that leverages the FastMCP library. The server is designed to expose a combination of both traditional synchronous tools and modern, I/O-bound asynchronous tools. However, it is currently afflicted by severe performance degradation, manifesting as client-side hanging and a failure to achieve true concurrency.  
The root of the problem lies in a flawed concurrency model that fundamentally misunderstands how to integrate asynchronous code into a mixed-paradigm application. Specifically, the server forces non-blocking asynchronous tools into a blocking, synchronous execution pattern. This is achieved by wrapping the asynchronous tool's coroutine in a call to asyncio.run() from within the server's synchronous request-handling logic. This misapplication of a core asyncio function effectively negates the primary benefit of asynchronous programming, causing the server's execution threads to block on I/O operations and rendering the entire system unresponsive.  
The objective of this document is to provide a definitive, production-grade architectural blueprint to resolve this issue. The proposed solution will detail a robust and scalable concurrency model that allows for the correct and efficient execution of both synchronous and asynchronous tools. This will be achieved by refactoring the server to properly manage the asyncio event loop, thereby eliminating performance bottlenecks and unlocking the full capabilities of the MCP framework.

### **1.3 Report Structure and Key Outcomes**

This report is structured to guide a technical lead or architect through a comprehensive analysis and resolution of the identified problem. It begins with a deep-dive analysis into the root cause, dissecting the behavior of asyncio.run() and explaining precisely why its use in a server context is an architectural anti-pattern. Following this diagnosis, the report will explore the native asynchronous capabilities of the FastMCP library, demonstrating that the framework itself provides the necessary building blocks for a correct implementation.  
The core of the report presents the solution: a robust architecture for mixed-concurrency tool execution based on a managed event loop running in a dedicated background thread. A detailed, step-by-step implementation guide will provide the necessary code and patterns to refactor the existing server. Finally, the report will analyze the profound impact of this new architecture, including the elimination of client hanging, the enablement of advanced MCP features like streaming progress updates, and the significant improvements in performance and scalability.  
Upon implementing the recommendations within this document, the MCP server will be transformed into a resilient, high-performance system. The desired end state is a server that:

* Executes asynchronous tools in a non-blocking, truly concurrent manner.  
* Maintains full compatibility with the existing suite of synchronous tools.  
* Completely eliminates the client-hanging behavior caused by blocked server threads.  
* Enables advanced, real-time features such as streaming progress reports for long-running tasks.  
* Maximizes throughput and optimizes performance for I/O-bound operations, aligning the server's capabilities with the foundational principles of the Model Context Protocol.

## **The Root Cause: A Deep Dive into asyncio.run() and Its Misapplication**

To architect a correct solution, it is first essential to perform a rigorous analysis of the underlying problem. The client hanging and performance issues stem from a fundamental misunderstanding of Python's asyncio library, specifically the function and purpose of asyncio.run(). This section deconstructs the flaw in the current architecture by examining the asyncio event loop, the specific behavior of asyncio.run(), and the cascading negative effects of its misuse in a long-running server application.

### **2.1 Understanding the asyncio Event Loop**

At the heart of any asyncio application is the event loop. It is the central scheduler that manages and executes asynchronous tasks, callbacks, and network I/O operations. The asyncio model in Python is based on cooperative multitasking within a single thread. This means that the event loop runs one task at a time. For other tasks to get a turn to run, the currently executing task must explicitly yield control back to the event loop. This yielding occurs whenever the await keyword is used on an awaitable object (such as a coroutine, a Future, or a Task).  
In the context of a network server, which is inherently I/O-bound, this model is exceptionally powerful. When a task performs a network operation (e.g., waiting for a response from a database or an external API), it can await the result. This action suspends the task and returns control to the event loop, which can then run other tasks that are ready to proceed. Once the network operation is complete, the event loop wakes up the original suspended task, allowing it to continue from where it left off. This cooperative yielding prevents a single long-running I/O operation from blocking the entire application, enabling a single thread to handle thousands of concurrent connections and operations efficiently.  
For a server application designed to run continuously and handle multiple client requests over its lifetime, the architectural best practice is to establish a single, persistent event loop that runs for the duration of the server process. This main event loop is responsible for managing all asynchronous operations, from accepting new connections to executing I/O-bound tool functions.

### **2.2 The Anti-Pattern: asyncio.run() in a Server Context**

The function asyncio.run() is a high-level, convenience function designed to be the main entry point for an asyncio program. Its behavior is very specific and deliberate:

1. It creates a **brand-new** asyncio event loop.  
2. It runs the single coroutine passed to it until that coroutine completes.  
3. It then performs a graceful shutdown of all associated tasks and generators.  
4. Finally, it **closes and destroys the event loop**.

This lifecycle makes asyncio.run() perfectly suited for simple scripts or for kicking off the primary main function of an application. However, its use inside a long-running server's request handler is a severe architectural anti-pattern. The current implementation, which calls asyncio.run(my\_async\_tool()) from within a synchronous dispatcher, triggers a destructive sequence of events for every asynchronous tool call.  
A detailed causal chain analysis reveals why this leads directly to the reported client hanging:

1. An MCP client, such as Claude Desktop or a VS Code extension, sends a request to the server to execute an asynchronous tool.  
2. The server's main thread, which is synchronous, receives this request and identifies the target asynchronous tool.  
3. The synchronous dispatcher then invokes asyncio.run() on the tool's coroutine.  
4. Crucially, the call to asyncio.run() is a **blocking call**. The server's main thread, which is responsible for communication with the client, now halts and waits for the entire asynchronous operation to complete. If the tool involves a 30-second API call, the thread is blocked for those 30 seconds.  
5. While this thread is blocked, it is completely unresponsive. It cannot process any other incoming requests from other clients, nor can it handle transport-level communication like keep-alive messages or progress updates for the current request.  
6. The MCP client, having sent its request, is now waiting for a response. It receives no communication from the server, not even an acknowledgment that the task has started. From the client's perspective, the server has simply stopped responding. This leads to the application "hanging" and, in many cases, eventually timing out and terminating the connection with an error.

The problem, however, extends beyond simple blocking. The repeated use of asyncio.run() introduces significant inefficiency and resource management issues. Each call creates and destroys an entire event loop, which carries a non-trivial computational overhead. More importantly, this pattern prevents the effective sharing of resources that are essential for high-performance I/O. For instance, best practices for asynchronous networking and database access involve creating a single aiohttp.ClientSession or a database connection pool when the application starts and reusing it for all subsequent operations. This amortizes the cost of connection setup and allows for optimizations like HTTP keep-alives. In the flawed architecture, each async tool runs in its own ephemeral, isolated event loop. It is impossible to share a ClientSession or a connection pool across these separate, short-lived loops. Consequently, each tool call must establish new connections, perform TLS handshakes, and then tear them down, adding significant latency and overhead to every operation. The architecture is actively fighting against the very efficiencies that asyncio is designed to provide.

### **2.3 Visualizing the Flaw: The Correct vs. Incorrect asyncio Model**

To provide absolute clarity on the correct application of asyncio functions, the following table contrasts the primary mechanisms for executing asynchronous code. It serves as a definitive guide for why asyncio.run() is unsuitable for this server context and highlights the appropriate tools for different concurrency scenarios.

| Function | Calling Context | Event Loop Behavior | Blocking Nature | Primary Use Case |
| :---- | :---- | :---- | :---- | :---- |
| await \<coroutine\> | Inside an async function | Runs the coroutine on the *current*, running event loop. | Asynchronous. Yields control to the event loop until the coroutine completes. | The standard way to call and wait for an async operation within another async function. |
| asyncio.create\_task() | Inside an async function | Schedules the coroutine to run on the *current* event loop as a background task. | Non-blocking. Returns an asyncio.Task object immediately. | "Fire-and-forget" tasks or running multiple operations concurrently without waiting for each one sequentially. |
| asyncio.run() | Synchronous code | **Creates a new event loop**, runs the coroutine, then **closes the loop**. | **Blocking.** Blocks the calling thread until the coroutine completes. | The main entry point for an entire asyncio application or simple script. **Not for use within a running application.** |
| loop.run\_until\_complete() | Synchronous code | Runs a future/coroutine on a *specified, existing* event loop until it completes. | **Blocking.** Blocks the calling thread until the future completes. | Lower-level alternative to asyncio.run() for integrating with an existing, manually managed loop. |
| loop.run\_in\_executor() | Inside an async function | Runs a *synchronous* function in a separate thread pool (ThreadPoolExecutor). | Asynchronous. Returns a future that completes when the synchronous function finishes. | Running blocking, CPU-bound code from an async function without blocking the event loop. |
| asyncio.run\_coroutine\_threadsafe() | Synchronous code (from a different thread) | Submits a coroutine to run on an event loop that is running in *another thread*. | Non-blocking. Returns a concurrent.futures.Future immediately. | The designated, thread-safe way to bridge synchronous and asynchronous code by scheduling work on a background event loop. |

*Table 1: Comparison of asyncio Execution Functions. Data compiled from.*  
This analysis unequivocally demonstrates that the current architecture's reliance on asyncio.run() is the direct cause of the observed performance issues. The correct architecture must replace this blocking, inefficient pattern with a model that maintains a persistent event loop and uses the appropriate non-blocking, thread-safe functions to schedule work upon it.

## **Leveraging FastMCP's Native Asynchronous Capabilities**

The architectural flaw does not lie within the FastMCP library itself. On the contrary, FastMCP is a modern, high-level framework specifically designed to embrace Python's asynchronous features. A thorough review of its capabilities reveals that it not only supports but actively encourages the use of async def for building responsive and powerful MCP tools. The solution, therefore, is not to work around FastMCP, but to use it as intended.

### **3.1 FastMCP: Designed for Asynchronicity**

FastMCP is a Pythonic framework that abstracts away the low-level complexities of the Model Context Protocol, allowing developers to focus on building tool functionality rather than managing protocol-level details like JSON-RPC message routing and connection management. It is part of a vibrant ecosystem of MCP libraries across different languages, including TypeScript and Ruby, all aiming to simplify server development. The Python version, particularly FastMCP 2.0, has evolved into a comprehensive platform with support for clients, server composition, and deployment tooling.  
A core design principle of FastMCP is its seamless support for both synchronous and asynchronous tools. The library provides a single, elegant decorator, @mcp.tool(), which can be applied to either a standard def function or an async def coroutine function. FastMCP automatically inspects the function signature and handles the invocation correctly, generating the necessary MCP schema from type hints and docstrings in both cases.  
This native support is evident in the library's documentation and examples, which frequently showcase asynchronous tools for any task that involves I/O, such as making network requests to external APIs. A canonical example of a well-formed asynchronous tool in FastMCP would be:  
`import httpx`  
`from fastmcp import FastMCP`

`mcp = FastMCP("WebSearcher")`

`@mcp.tool()`  
`async def search_web(query: str) -> str:`  
    `"""Performs a web search using an external API."""`  
    `async with httpx.AsyncClient() as client:`  
        `response = await client.get(f"https://api.example.com/search?q={query}")`  
        `response.raise_for_status()`  
        `return response.text`

This demonstrates that the framework is fully equipped to handle coroutines. The problem is not that FastMCP cannot run async tools, but that the server's execution environment is preventing it from doing so correctly.

### **3.2 The Context Object: A Window into the Async World**

The most compelling evidence of FastMCP's asynchronous design is the Context object. This special object can be injected as an argument into any tool function simply by adding a parameter with the type hint Context. The Context object serves as a bridge, giving the tool access to core MCP server capabilities during its execution.  
A close examination of the methods provided by the Context object is revealing. Key methods include:

* await ctx.report\_progress(current, total): For sending real-time progress updates to the client for long-running tasks.  
* await ctx.read\_resource(uri): For asynchronously reading data from another resource exposed by the server.  
* await ctx.sample(...): For making a request back to the client's LLM for sub-tasks or completions.  
* await ctx.info(...), await ctx.error(...), etc.: For asynchronous logging.

The critical observation here is that these are all **coroutines** that must be awaited. This design choice is a powerful architectural indicator. It signifies that the FastMCP framework fundamentally expects that any tool using the Context object is itself executing within a running, accessible asyncio event loop.  
This provides a definitive litmus test for the current flawed architecture. In the asyncio.run() model, the Context object would be created in the main synchronous thread, outside of the temporary event loop that asyncio.run() spins up to execute the tool. If a tool running inside this temporary loop were to call await ctx.report\_progress(), the report\_progress coroutine would attempt to run on the main thread's context, where there is no running event loop. This would inevitably raise a RuntimeError: no running event loop, causing the tool to crash.  
This confirms that the library's internal logic is predicated on the existence of a persistent, shared event loop that both the tool and the context's methods can access. The current architecture violates this fundamental assumption. The solution, therefore, must be one that establishes and maintains this persistent loop, allowing FastMCP's features to function as they were designed.

## **The Solution: A Robust Architecture for Mixed-Concurrency Tool Execution**

The resolution to the server's concurrency problems requires a fundamental architectural shift away from the asyncio.run() anti-pattern. The correct approach involves establishing a clear separation between synchronous and asynchronous execution contexts, creating a robust system that can handle any type of tool without blocking or contention. The proposed architecture is based on a well-established pattern for integrating asyncio into multithreaded applications: a managed event loop running in a dedicated background thread.

### **4.1 The Core Pattern: A Managed Event Loop in a Background Thread**

The central principle of the new architecture is to decouple the asyncio event loop from the main application thread(s) that handle incoming MCP requests. The server will be structured as follows:

1. **Main Server Thread(s):** These threads are responsible for the primary server logic, such as listening for connections and parsing incoming MCP messages. In a typical web server deployment, this would be the thread pool managed by a server like Uvicorn or Gunicorn. This layer remains synchronous.  
2. **Dedicated asyncio Event Loop Thread:** A single, persistent background threading.Thread is created when the server starts. The sole purpose of this thread is to run the asyncio event loop for the entire lifecycle of the application.

This pattern creates a stable, long-running asynchronous execution context that is completely independent of the synchronous request-handling threads. It provides a bridge between the two paradigms, allowing the synchronous part of the application to safely offload asynchronous work to the asyncio world without blocking itself. This approach is a standard and recommended practice for mixing synchronous and asynchronous code in Python, as demonstrated in numerous community examples and technical discussions.

### **4.2 Executing Asynchronous Tools: The Role of asyncio.run\_coroutine\_threadsafe**

With a persistent event loop running in a background thread, the challenge becomes how to safely submit work to it from the main synchronous threads. The function designed precisely for this purpose is asyncio.run\_coroutine\_threadsafe(). This function is the designated, thread-safe mechanism for scheduling a coroutine to be executed on an event loop that is running in a different thread.  
The execution flow for an asynchronous tool under this new architecture is as follows:

1. The main server thread receives an MCP request to execute an async tool.  
2. Instead of blocking, the synchronous dispatcher calls asyncio.run\_coroutine\_threadsafe(async\_tool\_coroutine, background\_loop).  
3. This call is **non-blocking**. It immediately returns a concurrent.futures.Future object and allows the main thread to continue its work, such as handling other incoming requests.  
4. The event loop, running in the background thread, picks up the submitted async\_tool\_coroutine from its queue and begins executing it.  
5. When the synchronous dispatcher needs the result of the tool to send back to the client, it calls .result() on the Future object. This call will block the dispatcher thread, but critically, it only blocks until that *one specific task* is complete. It does not block the asyncio event loop, which remains free to run other concurrent async tasks. It also does not block the entire server process, just the thread waiting for that specific result.

### **4.3 Handling Synchronous Tools: The Role of loop.run\_in\_executor**

A comprehensive solution must also account for the existing synchronous tools, ensuring they can run efficiently without disrupting the new asynchronous core. Simply running a long, blocking synchronous function (e.g., a CPU-intensive calculation) directly on the asyncio event loop would be disastrous, as it would freeze the entire loop and all other async tasks.  
The correct way to handle blocking synchronous code from within an asyncio context is loop.run\_in\_executor(). This method takes a regular synchronous function and runs it in a separate thread pool (a concurrent.futures.ThreadPoolExecutor), effectively isolating its blocking behavior from the event loop.  
The execution flow for a synchronous tool is slightly different, involving a handoff to the async world first:

1. The main server thread receives a request for a synchronous tool.  
2. The dispatcher submits a small wrapper coroutine to the background event loop using asyncio.run\_coroutine\_threadsafe.  
3. This wrapper coroutine, now executing on the event loop, calls await loop.run\_in\_executor(None, sync\_tool\_function, \*args).  
4. The sync\_tool\_function is now executed by a worker thread from the default thread pool, performing its blocking work without affecting the event loop.  
5. The await on run\_in\_executor completes only when the synchronous tool finishes its execution in the worker thread. The result is then propagated back through the Future to the main thread that is waiting for it.

This three-tiered architecture—a main synchronous router, a dedicated asynchronous I/O thread, and a worker pool for synchronous tasks—creates an exceptionally robust and flexible concurrency model. It does more than just fix the immediate bug; it establishes a future-proof pattern for the server. The main thread becomes a lightweight request dispatcher. The asyncio event loop becomes a highly efficient engine for all I/O-bound operations. The executor thread pool handles any CPU-bound or legacy blocking code. This clean separation of concerns ensures that the server is scalable, maintainable, and resilient. Adding new tools in the future, whether they are quick API calls or long-running data processing jobs, will require no further architectural changes, as the dispatcher can intelligently route the workload to the appropriate execution context.

## **Implementation Guide: Refactoring the MCP Server**

This section provides a concrete implementation of the proposed architecture. It includes a reusable class for managing the asynchronous execution context and a unified dispatcher for handling both synchronous and asynchronous tools. This guide is designed to be a practical, step-by-step blueprint for refactoring the existing MCP server.

### **5.1 The AsyncToolExecutor Class: Managing the Lifecycle**

To encapsulate the logic for managing the background thread and the asyncio event loop, we will create a dedicated AsyncToolExecutor class. This class will handle the startup, shutdown, and thread-safe submission of tasks, providing a clean interface for the rest of the application. The design is based on established best practices for mixing threading and asyncio.  
`import asyncio`  
`import threading`  
`from concurrent.futures import Future`  
`from typing import Callable, Coroutine, Any`

`class AsyncToolExecutor:`  
    `"""`  
    `Manages a dedicated asyncio event loop running in a background thread`  
    `to execute asynchronous tools in a non-blocking, thread-safe manner.`  
    `"""`  
    `def __init__(self):`  
        `self._loop = None`  
        `self._thread = None`  
        `self._startup_event = threading.Event()`

    `def start(self):`  
        `"""Starts the background thread and the asyncio event loop."""`  
        `if self._thread is not None:`  
            `return  # Already started`

        `self._thread = threading.Thread(target=self._run_loop, daemon=True)`  
        `self._thread.start()`  
        `# Wait until the loop is running in the background thread`  
        `self._startup_event.wait()`  
        `print("AsyncToolExecutor started with event loop.")`

    `def stop(self):`  
        `"""Stops the event loop and joins the background thread gracefully."""`  
        `if self._thread is None or self._loop is None:`  
            `return`

        `# Schedule the loop to stop from the loop's own thread`  
        `self._loop.call_soon_threadsafe(self._loop.stop)`  
        `self._thread.join()`  
        `self._thread = None`  
        `self._loop = None`  
        `print("AsyncToolExecutor stopped.")`

    `def _run_loop(self):`  
        `"""The target function for the background thread."""`  
        `try:`  
            `self._loop = asyncio.new_event_loop()`  
            `asyncio.set_event_loop(self._loop)`  
            `# Signal that the loop is set up and running`  
            `self._startup_event.set()`  
            `self._loop.run_forever()`  
        `finally:`  
            `self._loop.close()`

    `def submit_async(self, coro: Coroutine) -> Future:`  
        `"""`  
        `Thread-safely submits an asynchronous coroutine to the event loop.`

        `Args:`  
            `coro: The coroutine to execute.`

        `Returns:`  
            `A concurrent.futures.Future that will hold the result.`  
        `"""`  
        `if not self._loop:`  
            `raise RuntimeError("Executor is not running. Call start() first.")`  
        `return asyncio.run_coroutine_threadsafe(coro, self._loop)`

    `def submit_sync(self, func: Callable, *args: Any) -> Coroutine:`  
        `"""`  
        `Creates a coroutine that runs a synchronous function in a thread pool`  
        `to avoid blocking the event loop.`

        `Args:`  
            `func: The synchronous function to execute.`  
            `args: Arguments to pass to the function.`

        `Returns:`  
            `A coroutine that, when awaited, will execute the sync function.`  
        `"""`  
        `if not self._loop:`  
            `raise RuntimeError("Executor is not running. Call start() first.")`  
        `# loop.run_in_executor runs the sync function in the default ThreadPoolExecutor`  
        `return self._loop.run_in_executor(None, func, *args)`

    `def __enter__(self):`  
        `self.start()`  
        `return self`

    `def __exit__(self, exc_type, exc_val, exc_tb):`  
        `self.stop()`

This class can be used as a context manager to ensure that the background thread is properly started and stopped with the server's lifecycle.

### **5.2 A Unified Tool Dispatcher**

With the AsyncToolExecutor in place, the next step is to create a unified dispatcher within the main server logic. This dispatcher will determine whether a tool is synchronous or asynchronous and use the appropriate submission method. The inspect.iscoroutinefunction() method is the key to this differentiation.  
Here is an example of how this dispatcher could be integrated into a simplified server structure:  
`import inspect`

`class MyMCPServer:`  
    `def __init__(self):`  
        `self.tools = {}  # A dictionary mapping tool names to functions`  
        `self.executor = AsyncToolExecutor()`

    `def register_tool(self, func: Callable):`  
        `"""Registers a tool function."""`  
        `self.tools[func.__name__] = func`

    `def start_server(self):`  
        `"""Starts the server and the async executor."""`  
        `self.executor.start()`  
        `#... other server startup logic...`

    `def stop_server(self):`  
        `"""Stops the server and the async executor."""`  
        `self.executor.stop()`  
        `#... other server shutdown logic...`

    `def handle_tool_request(self, tool_name: str, params: dict) -> Any:`  
        `"""`  
        `The main dispatch logic for handling an incoming tool call.`  
        `"""`  
        `if tool_name not in self.tools:`  
            `raise ValueError(f"Tool '{tool_name}' not found.")`

        `tool_func = self.tools[tool_name]`

        `# Differentiate between sync and async tools`  
        `if inspect.iscoroutinefunction(tool_func):`  
            `# It's an async tool`  
            `print(f"Dispatching ASYNC tool: {tool_name}")`  
            `coro = tool_func(**params)`  
            `future = self.executor.submit_async(coro)`  
        `else:`  
            `# It's a sync tool`  
            `print(f"Dispatching SYNC tool: {tool_name}")`  
            `# Wrap the sync call in run_in_executor via a coroutine,`  
            `# then submit that coroutine to the event loop.`  
            `coro = self.executor.submit_sync(tool_func, **params)`  
            `future = self.executor.submit_async(coro)`

        `# Block and wait for the result. This is safe because the actual`  
        `# work is happening in other threads (the event loop thread or`  
        `# the executor's thread pool).`  
        `try:`  
            `# Add a timeout to prevent indefinite hanging`  
            `result = future.result(timeout=60.0)`  
            `print(f"Tool '{tool_name}' completed with result: {result}")`  
            `return result`  
        `except Exception as e:`  
            `print(f"Tool '{tool_name}' failed with an exception: {e}")`  
            `# Propagate the error to the MCP client`  
            `raise`

### **5.3 Refactored Tool Examples (Before and After)**

To illustrate the simplicity and power of this new architecture, let's look at how existing tools would be refactored.

#### **Asynchronous Tool: fetch\_web\_page**

This tool performs a network I/O operation and is a prime candidate for asynchronicity.

* **Before (Flawed Architecture):** The implementation likely involved a synchronous wrapper function that called asyncio.run() internally, leading to blocking.  
  `# OLD, FLAWED IMPLEMENTATION`  
  `import asyncio`  
  `import httpx`

  `async def _real_fetch(url):`  
      `async with httpx.AsyncClient() as client:`  
          `return await client.get(url)`

  `def fetch_web_page(url: str):`  
      `# This blocks the entire server thread!`  
      `return asyncio.run(_real_fetch(url))`

* **After (Correct Architecture):** The tool is now a simple, clean async def coroutine. The complexity is handled by the dispatcher, not the tool itself.  
  `# NEW, CORRECT IMPLEMENTATION`  
  `import httpx`

  `async def fetch_web_page(url: str) -> str:`  
      `"""Asynchronously fetches the content of a URL."""`  
      `async with httpx.AsyncClient() as client:`  
          `response = await client.get(url)`  
          `response.raise_for_status()`  
          `return response.text`

#### **Synchronous Tool: calculate\_fibonacci**

This tool performs a CPU-bound calculation. It should not be modified, but the new architecture ensures it runs without blocking the event loop.

* **Before (Potentially Blocking):** A standard synchronous function. In the old architecture, if called frequently, it could still contribute to server sluggishness. In the new architecture, it must be handled correctly to avoid blocking the async event loop.  
  `# SYNCHRONOUS IMPLEMENTATION (UNCHANGED)`  
  `def calculate_fibonacci(n: int) -> int:`  
      `"""A CPU-bound synchronous function."""`  
      `if n <= 1:`  
          `return n`  
      `else:`  
          `return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)`

* **After (Correctly Dispatched):** The function definition remains identical. The change is in how the dispatcher handles it. The dispatcher will recognize it as a synchronous function and use executor.submit\_sync, which wraps it in loop.run\_in\_executor. This offloads the blocking work to a separate thread pool, keeping the main asyncio event loop responsive for other I/O-bound tasks. The developer writing the tool needs to make no changes.

This refactoring delivers a clean separation of concerns. Tool developers can write straightforward synchronous or asynchronous functions without worrying about the underlying concurrency model. The server's central AsyncToolExecutor and dispatcher handle the complex task of executing them efficiently and safely.

## **Client-Side Impact and Unlocking Advanced Capabilities**

Adopting the proposed mixed-concurrency architecture does more than just fix a server-side bug; it fundamentally transforms the capabilities of the MCP server and dramatically improves the experience for the end-user interacting with the MCP client. The resolution of the core blocking issue has cascading positive effects, eliminating client-side hangs and enabling a new class of advanced, real-time features that were previously impossible.

### **6.1 Eliminating Client Hanging**

The most immediate and critical impact of this architectural refactoring is the complete elimination of the client hanging issue. As established, the previous architecture caused the server's main communication thread to block during any asynchronous tool execution. This left the client application—be it Claude Desktop, a VS Code extension, or another MCP-compatible host—in a state of limbo, waiting for a response from a server that was effectively deaf to the network. User reports across community forums and GitHub issues frequently describe this exact behavior: tools that "hang forever" or clients that freeze upon tool invocation, particularly when the server is running on certain platforms or when using specific transport protocols.  
The new architecture directly resolves this. By offloading all tool execution (both sync and async) to background threads, the server's main thread(s) remain free and responsive. They can continue to handle the underlying transport protocol, responding to network health checks, processing keep-alive messages, and managing the client connection state. The client no longer experiences unexplained timeouts or freezes because the server remains communicative throughout the entire lifecycle of a tool call. This restores reliability and trust in the server's operation.

### **6.2 Enabling Streaming and Progress Updates**

The Model Context Protocol was explicitly designed to support more than just simple request-response interactions. Its support for transports like Server-Sent Events (SSE) is intended to enable real-time, server-pushed data streams. This capability is crucial for long-running tasks, where providing intermediate feedback to the user is essential for a good experience.  
The FastMCP library exposes this capability through the await ctx.report\_progress() method. With the non-blocking architecture now in place, this feature becomes fully functional. An asynchronous tool can perform a multi-step process and yield control back to the event loop at each stage, sending progress updates along the way.  
Consider a tool that processes a large file:  
`import asyncio`  
`from fastmcp import Context`

`async def process_large_file(file_path: str, ctx: Context) -> str:`  
    `"""Processes a large file and reports progress to the client."""`  
    `await ctx.info(f"Starting to process file: {file_path}")`  
    `await ctx.report_progress(progress=0, total=100)`

    `# Simulate Step 1: Reading the file`  
    `await asyncio.sleep(5) # Represents a long I/O operation`  
    `await ctx.info("File reading complete.")`  
    `await ctx.report_progress(progress=33, total=100)`

    `# Simulate Step 2: Analyzing data`  
    `await asyncio.sleep(10) # Represents a long I/O or async computation`  
    `await ctx.info("Data analysis complete.")`  
    `await ctx.report_progress(progress=66, total=100)`

    `# Simulate Step 3: Generating report`  
    `await asyncio.sleep(5) # Represents a final I/O operation`  
    `await ctx.info("Report generation complete.")`  
    `await ctx.report_progress(progress=100, total=100)`

    `return "Processing complete."`

In the old, blocking architecture, this tool would have been impossible to implement correctly. The server would block for the full 20 seconds, and all progress reports would be buffered and delivered in a single burst at the very end, if at all. In the new architecture, the client would receive four distinct progress updates in real-time as the task executes, providing a responsive and interactive experience.

### **6.3 True Concurrency in Action**

Beyond handling single tasks gracefully, the new architecture unlocks true concurrency, dramatically increasing the server's throughput. Because the asyncio event loop is never blocked, it can manage the execution of multiple asynchronous tools simultaneously.  
Imagine a scenario where two different clients make requests to the server at nearly the same time:

* Client A calls an async tool that takes 10 seconds to query a remote API.  
* Client B calls another async tool that takes 12 seconds to access a database.

In the old, blocking architecture, these requests would be serialized. The server would block for 10 seconds on Client A's request, and only after it completed would it begin Client B's 12-second request. The total time to serve both clients would be 22 seconds.  
In the new, non-blocking architecture, the event loop will handle both tasks concurrently. It will initiate the API query for Client A, and while waiting for the network response, it will initiate the database query for Client B. The event loop will efficiently interleave the execution of both tasks as they wait for their respective I/O operations to complete. The total time to serve both clients would be approximately 12 seconds (the duration of the longest task), not 22\. This represents a nearly 2x improvement in throughput. This aligns directly with the performance benefits cited for asynchronous MCP systems, which can see task processing speed increases of up to 300% under I/O-bound loads. This ability to handle multiple concurrent operations efficiently is the hallmark of a scalable, production-ready server.

## **Performance, Scalability, and Production Considerations**

Transitioning to the correct concurrency model is the most critical step, but building a truly production-ready MCP server requires further attention to performance tuning, robust error handling, and deployment best practices. The new architecture serves as a solid foundation upon which these additional layers of resilience and operational excellence can be built.

### **7.1 Performance Analysis**

The performance difference between the flawed asyncio.run() architecture and the proposed background event loop architecture is not incremental; it is transformative. The primary gains are in latency under concurrency and overall server throughput.

* **Latency:** For a single, isolated tool call, the latency might be comparable. However, in any real-world scenario with multiple concurrent clients, the old architecture exhibits catastrophic latency degradation. As requests queue up behind a single blocked thread, wait times increase linearly. The new architecture maintains low latency for new requests even while existing long-running tasks are in flight, as the dispatcher remains responsive.  
* **Throughput:** For I/O-bound workloads, the new architecture's throughput will be orders of magnitude higher. By interleaving I/O waits, the server can make progress on many tasks simultaneously, fully utilizing the available network and I/O capacity. This directly enables the kind of performance improvements—such as a 300% increase in task processing throughput and a 70-80% reduction in average response times—that are characteristic of well-designed asynchronous systems.  
* **Resource Utilization:** The new model is also more resource-efficient. By eliminating the constant creation and destruction of event loops and enabling the reuse of resources like aiohttp.ClientSession or database connection pools, the server reduces CPU overhead and memory churn.

### **7.2 Error Handling and Timeouts**

A production system must be resilient to failure. The proposed architecture provides clear mechanisms for handling errors and timeouts.

* **Error Propagation:** Any exception raised within a tool function, whether synchronous or asynchronous, will be captured by the Future object returned by the submission call. When .result() is called on this future in the main thread, the exception is re-raised, allowing the dispatcher to catch it and formulate a proper MCP error response to send to the client. This ensures that tool failures are handled gracefully and donot crash the server.  
* **Timeouts:** The server must protect itself from tools that hang indefinitely. The concurrent.futures.Future object provides a direct mechanism for this. The call future.result(timeout=60.0) will wait for a maximum of 60 seconds. If the tool has not completed by then, a TimeoutError is raised, which the dispatcher can handle appropriately, perhaps by sending a cancellation notification to the client and logging the failure. For more granular control within asynchronous code, the asyncio.timeout() context manager can be used inside a tool's coroutine to enforce time limits on specific await calls.

### **7.3 Production Deployment and Architecture**

While the core logic is sound, deploying this server requires adherence to modern operational standards.

* **Deployment:** The server application should be containerized using Docker. This creates a consistent, reproducible environment. For production scaling, this container should be deployed using an orchestration platform like Kubernetes or a managed service such as AWS ECS or Google Cloud Run. These platforms provide automated scaling, load balancing, and health checks, restarting unhealthy server instances automatically.  
* **Security:** As with any service that can execute arbitrary code, security is paramount. The MCP specification itself outlines key principles that must be respected, including obtaining explicit user consent before executing any tool and ensuring data privacy. The server should be deployed behind a load balancer that enforces HTTPS with TLS termination.  
* **Architectural Choice and Trade-offs:** The decision to use this hybrid thread/async architecture is a pragmatic one, tailored to the problem of integrating a mixed codebase. For projects starting from scratch or already built on an async-native web framework, using a library like fastapi-mcp could be a more direct path. That library automatically converts FastAPI endpoints into MCP tools, leveraging FastAPI's native async capabilities and dependency injection system. However, the user's situation implies a need to support an existing set of synchronous tools alongside new asynchronous ones. The proposed architecture acts as an "architectural bridge," allowing legacy synchronous code to coexist with modern, high-performance asynchronous code without requiring a complete rewrite of the entire application. This pattern acknowledges the realities of evolving enterprise systems. Developers should remain mindful, however, that such hybrid models can introduce complexities, particularly around observability. As seen in experiments running FastMCP on serverless platforms like AWS Lambda, unifying logging and tracing across synchronous threads, asyncio loops, and framework logic can be challenging and may require custom middleware or careful configuration.

## **Conclusion**

The critical performance issues of client hanging and lack of concurrency within the MCP server are the direct result of a flawed architectural pattern that misuses asyncio.run(). This function, designed as a top-level entry point, creates and destroys an event loop for every call, blocking the server's main thread and preventing the very concurrency it aims to achieve. This anti-pattern not only degrades performance but also makes it impossible to implement advanced, real-time MCP features.  
The definitive solution is to re-architect the server's concurrency model to align with the design principles of both asyncio and the FastMCP library. This involves implementing a robust, three-tiered system:

1. A main synchronous layer for request handling.  
2. A dedicated background thread running a persistent asyncio event loop for all I/O-bound operations.  
3. A thread pool executor for safely running legacy or CPU-bound synchronous code without blocking the event loop.

Communication between these layers is managed by the appropriate thread-safe asyncio functions: asyncio.run\_coroutine\_threadsafe to submit work to the event loop, and loop.run\_in\_executor to offload blocking tasks from it.  
By adopting this architecture, the MCP server will be transformed from a fragile, underperforming application into a scalable, resilient, and highly concurrent system. This change will not only resolve the immediate client-hanging issues but will also unlock the full potential of the Model Context Protocol, enabling true concurrency, real-time progress streaming, and significantly higher throughput. This provides a future-proof foundation capable of supporting a diverse and growing suite of both synchronous and asynchronous tools, fully realizing the promise of a truly interactive and agentic AI experience.

#### **Works cited**

1\. en.wikipedia.org, https://en.wikipedia.org/wiki/Model\_Context\_Protocol 2\. Welcome to FastMCP 2.0\! \- FastMCP, https://gofastmcp.com/getting-started/welcome 3\. Model Context Protocol: Introduction, https://modelcontextprotocol.io/ 4\. The Easiest Way to Understand Model Context Protocol (MCP) with code, https://dhnanjay.medium.com/the-easiest-way-to-understand-model-context-protocol-mcp-with-code-15fe3b302205 5\. Introducing the StreamNative MCP Server: Connecting Streaming Data to AI Agents, https://streamnative.io/blog/introducing-the-streamnative-mcp-server-connecting-streaming-data-to-ai-agents 6\. Still Confused About How MCP Works? Here's the Explanation That Finally Made it Click For Me : r/ClaudeAI \- Reddit, https://www.reddit.com/r/ClaudeAI/comments/1ioxu5r/still\_confused\_about\_how\_mcp\_works\_heres\_the/ 7\. www.byteplus.com, https://www.byteplus.com/en/topic/541919\#:\~:text=Async%20MCP%20is%20fundamentally%20designed,effectively%20multiplying%20your%20computational%20throughput. 8\. MCP Async Processing: Guide to Model Context Protocol \- BytePlus, https://www.byteplus.com/en/topic/541919 9\. MCP Streaming Responses: How It Works & Implementation Guide \- BytePlus, https://www.byteplus.com/en/topic/541918 10\. What are the specific use-cases for threading over using asyncio? : r/Python \- Reddit, https://www.reddit.com/r/Python/comments/p726gm/what\_are\_the\_specific\_usecases\_for\_threading\_over/ 11\. Coroutines and Tasks — Python 3.13.5 documentation, https://docs.python.org/3/library/asyncio-task.html 12\. Event Loop — Python 3.13.5 documentation, https://docs.python.org/3/library/asyncio-eventloop.html 13\. MCP Servers work in Cline but fail in Claude Desktop : r/ClaudeAI \- Reddit, https://www.reddit.com/r/ClaudeAI/comments/1ipvo9k/mcp\_servers\_work\_in\_cline\_but\_fail\_in\_claude/ 14\. MCP SDK hangs · Issue \#813 · modelcontextprotocol/python-sdk \- GitHub, https://github.com/modelcontextprotocol/python-sdk/issues/813 15\. Chat freezes on MCP tool call, mcp works w/ other apps \- Bug Reports \- Cursor Forum, https://forum.cursor.com/t/chat-freezes-on-mcp-tool-call-mcp-works-w-other-apps/77834 16\. python \- What's the difference between these functions \- Stack Overflow, https://stackoverflow.com/questions/71089837/whats-the-difference-between-these-functions 17\. asyncio.run\_coroutine\_threadsafe API | by alex\_ber \- Medium, https://alex-ber.medium.com/asyncio-run-coroutine-threadsafe-api-d24cc56a5255 18\. Developing with asyncio — Python 3.13.5 documentation, https://docs.python.org/3/library/asyncio-dev.html 19\. How to properly use asyncio run\_coroutine\_threadsafe function? \- Stack Overflow, https://stackoverflow.com/questions/60113143/how-to-properly-use-asyncio-run-coroutine-threadsafe-function 20\. FastMCP: The fastway to build MCP servers. | by CellCS \- Medium, https://medium.com/@shmilysyg/fastmcp-the-fastway-to-build-mcp-servers-aa14f88536d2 21\. fastmcp·PyPI, https://pypi.org/project/fastmcp/1.0/ 22\. jlowin/fastmcp: The fast, Pythonic way to build MCP servers and clients \- GitHub, https://github.com/jlowin/fastmcp 23\. punkpeye/fastmcp: A TypeScript framework for building MCP servers. \- GitHub, https://github.com/punkpeye/fastmcp 24\. yjacquin/fast-mcp: A Ruby Implementation of the Model Context Protocol \- GitHub, https://github.com/yjacquin/fast-mcp 25\. A Beginner's Guide to Use FastMCP \- Apidog, https://apidog.com/blog/fastmcp/ 26\. AI-App/JLowin.FastMCP: The fast, Pythonic way to build MCP servers and clients \- GitHub, https://github.com/AI-App/JLowin.FastMCP 27\. fastmcp \- PyPI, https://pypi.org/project/fastmcp/2.2.6/ 28\. Tools \- FastMCP, https://gofastmcp.com/servers/tools 29\. For Server Developers \- Model Context Protocol, https://modelcontextprotocol.io/quickstart/server 30\. How to create a threadpool with its own async loop separated from the main thread, https://discuss.python.org/t/how-to-create-a-threadpool-with-its-own-async-loop-separated-from-the-main-thread/77734 31\. Python asyncio event loop in a separate thread · GitHub, https://gist.github.com/dmfigol/3e7d5b84a16d076df02baa9f53271058 32\. How do I set the asyncio event loop for a thread in Python? \- Stack Overflow, https://stackoverflow.com/questions/52298922/how-do-i-set-the-asyncio-event-loop-for-a-thread-in-python 33\. SystemExit Hangs asyncio.run\_coroutine\_threadsafe \- Chi-Sheng Liu, https://chishengliu.com/posts/run-coroutine-threadsafe-systemexit/ 34\. How to Fix Claude Desktop MCP Issues on Windows 11: A Complete Guide \- Neoh, https://www.eudaimoniatech.io/how-to-fix-claude-desktop-mcp-issues-on-windows-11-a-complete-guide/ 35\. Transports \- Model Context Protocol, https://modelcontextprotocol.io/specification/2025-03-26/basic/transports/ 36\. What's the best way to deploy an Model Context Protocol (MCP) server to production?, https://milvus.io/ai-quick-reference/whats-the-best-way-to-deploy-an-model-context-protocol-mcp-server-to-production 37\. Specification \- Model Context Protocol, https://modelcontextprotocol.io/specification/2025-06-18 38\. tadata-org/fastapi\_mcp: Expose your FastAPI endpoints as ... \- GitHub, https://github.com/tadata-org/fastapi\_mcp 39\. How to Use FastAPI MCP Server \- Apidog, https://apidog.com/blog/fastapi-mcp/ 40\. Add MCP Server to Any FastAPI App in 5 Minutes \- YouTube, https://www.youtube.com/watch?v=1GshZTn\_6qE\&pp=0gcJCfwAo7VqN5tD 41\. I Tried Running an MCP Server on AWS Lambda… Here's What Happened \- Ran The Builder, https://www.ranthebuilder.cloud/post/mcp-server-on-aws-lambda