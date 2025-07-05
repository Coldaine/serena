## Knowledge Agent Query: Understanding Serena's Prompt System and Tool Call Timing

### Context
I am working on the Serena MCP (Model Context Protocol) server project, which is an advanced AI coding assistant. We've identified communication reliability issues where tool calls are executed successfully on the server but results don't consistently reach the client, causing timeouts and "cancellation" errors.

### Repository Information
- **Repository**: https://github.com/Coldaine/serena (fork of https://github.com/oraios/serena)
- **Language**: Python
- **Architecture**: MCP server with async tool execution, language server integration, and AI agent capabilities

### Specific Questions I Need Answered

#### 1. **Initial Instructions and System Prompts**
- How does Serena construct its initial instructions/system prompts for AI agents?
- Where are the prompt templates stored and how are they structured?
- What is the relationship between `agent.py`, `prompt_factory.py`, and the template system?
- How can I modify the system prompt to include better guidance about tool call timing?

#### 2. **Tool Call Execution Flow**
- What is the complete flow from when an agent makes a tool call to when it receives the result?
- How does the `AsyncToolExecutor` integrate with the MCP server's response system?
- Where in the code should I add instructions about waiting for tool call results?
- Are there timeout configurations that agents should be aware of?

#### 3. **Agent Behavior and Configuration**
- How does Serena configure agent behavior regarding tool call patience?
- Are there existing mechanisms for agents to understand when to wait vs. when to timeout?
- What role does the `UnifiedToolDispatcher` play in agent interactions?
- How can I communicate retry logic and timeout expectations to agents?

#### 4. **Prompt Engineering Best Practices**
- What are the best practices for instructing AI agents about asynchronous operations?
- How should I phrase instructions about waiting for tool call results?
- What specific language would be most effective for preventing premature timeouts?
- Are there examples of similar systems that handle this well?

#### 5. **Configuration and Context Files**
- What files control agent behavior and initial instructions?
- How do I ensure new instructions are properly loaded and applied?
- Are there configuration files (YAML, JSON) that might contain timeout settings?
- What is the relationship between `serena_config.yml` and agent behavior?

### Specific Code Files to Examine
Based on the repository structure, please pay particular attention to:
- `src/serena/agent.py` - Main agent implementation
- `src/serena/prompt_factory.py` - Prompt construction logic
- `src/serena/async_tool_executor.py` - Async tool execution (recently enhanced)
- `src/serena/mcp.py` - MCP server integration
- `src/interprompt/` - Prompt templating system
- `serena_config.yml` - Configuration file
- Any template files in `src/serena/resources/` or similar directories

### The Problem I'm Trying to Solve
**Issue**: AI agents are timing out or "cancelling" tool calls that are actually executing successfully on the server side.

**Goal**: Modify Serena's initial instructions to include guidance like:
- "Wait patiently for tool call results - they may take time to execute"
- "Tool calls are executed asynchronously and may take 30-300 seconds"
- "If a tool call appears to timeout, it may still be executing - avoid making duplicate calls"
- "Use retry logic intelligently - some delays are normal"

### Expected Deliverables
Please provide:
1. **Architecture Overview**: How Serena's prompt system works
2. **File Locations**: Exact files where initial instructions are defined
3. **Modification Strategy**: Step-by-step approach to add timing guidance
4. **Code Examples**: Specific code snippets showing where/how to make changes
5. **Best Practices**: Recommended language for the new instructions
6. **Testing Approach**: How to verify the changes work properly

### Additional Context
- We've already enhanced the `AsyncToolExecutor` with retry logic and better error handling
- The communication issues seem to be infrastructure-related, not tool execution problems
- We need to educate agents about the async nature of the system
- The solution should be maintainable and not break existing functionality

Please analyze the repository thoroughly and provide a comprehensive understanding of how to implement these improvements effectively.
