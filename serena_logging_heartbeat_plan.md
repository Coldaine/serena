# Serena MCP Logging and Heartbeat Enhancement Plan

## 1. Log the Listening Port on Startup
- After the server binds to a port, add a log statement:
  - Example: `[INFO] Serena MCP started on port 8032`
- Use the existing logging framework (Python `logging` or the project's logger).
- Place this log message immediately after the port is bound and before the server starts accepting connections.

## 2. Add a Heartbeat Log
- Start a background thread or async task after the server starts.
- This thread logs a heartbeat message every N seconds (e.g., 60 seconds):
  - Example: `[HEARTBEAT] Serena MCP alive at 2025-06-30 14:00:00`
- Use the same logger so the heartbeat appears in both the log file and the GUI log window.
- Example implementation (Python):
  ```python
  import threading, time, logging
  def heartbeat():
      while True:
          logging.info(f"HEARTBEAT: Serena MCP is alive at {time.strftime('%Y-%m-%d %H:%M:%S')}")
          time.sleep(60)
  threading.Thread(target=heartbeat, daemon=True).start()
  ```

## 3. Log File Location (Optional)
- Ensure logs are written to a file (e.g., `serena-mcp.log`) for later review.
- If not already configured, set up logging to file:
  ```python
  logging.basicConfig(filename='serena-mcp.log', level=logging.INFO)
  ```

## 4. GUI Log Window
- The GUI log window should display all log messages, including the port and heartbeat.
- If the GUI uses the same logger, no extra work is needed.

## 5. Implementation Steps
1. Locate the main server startup code (likely in `src/serena` or `src/solidlsp`).
2. Add a log statement after binding to the port.
3. Add a heartbeat thread as shown above.
4. Confirm that the logger outputs to both file and GUI.
5. Test by starting the server and checking the log for port and heartbeat messages.

## 6. Summary Table
| Change                | What to Do                                      |
|-----------------------|-------------------------------------------------|
| Log port on startup   | Add log/print after binding to port             |
| Heartbeat log         | Add background thread/task to log periodically  |
| Log file (optional)   | Ensure logs go to a file for review             |

---

**This plan will make it easy to see which port Serena MCP is listening on and confirm that the server is still alive via the logs and GUI.**
