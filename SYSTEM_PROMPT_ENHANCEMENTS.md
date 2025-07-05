# System Prompt Enhancements for Tool Call Reliability

## Overview

This document describes the enhancements made to Serena's system prompt to improve agent behavior regarding tool call timeouts and communication reliability.

## Problem Addressed

**Root Issue**: AI agents were timing out or "cancelling" tool calls that were actually executing successfully on the server side, leading to:
- Premature timeout assumptions
- Duplicate tool calls
- Poor user experience
- Communication reliability issues

## Solution Implemented

### Enhanced System Prompt

Modified `src/serena/resources/config/prompt_templates/system_prompt.yml` to include a new dedicated section: **"Tool Execution Guidelines - IMPORTANT"**

#### Key Guidelines Added:

1. **Patience and Timing**
   - Wait patiently for tool results (3-4 minute normal timeout)
   - Don't assume failure on lack of immediate response
   - Some delays are normal and expected

2. **Duplicate Call Prevention**
   - Avoid making duplicate tool calls
   - Tools that appear cancelled may still be executing
   - Trust the server-side process

3. **Intelligent Retry Logic**
   - Only retry after clear failure confirmation
   - Use retry logic intelligently
   - Wait for full timeout period before retrying

4. **Communication Awareness**
   - Tools that appear "cancelled" may have completed successfully
   - Infrastructure has built-in retry logic and error handling
   - Communication delays ≠ tool failure

### Implementation Details

#### Files Modified:

1. **`src/serena/resources/config/prompt_templates/system_prompt.yml`**
   - Added comprehensive "Tool Execution Guidelines" section
   - Positioned prominently at the top of the prompt
   - Used strong, imperative language for clear instruction

2. **`src/serena/agent.py`** (temporary enhancement)
   - Added logging to verify prompt loading
   - Confirms guidelines are active in system prompt

#### Configuration Integration:

The guidelines reference the actual timeout configuration:
- **Current timeout**: 3 minutes (180 seconds) from `serena_config.yml`
- **Default timeout**: 4 minutes (240 seconds) from `DEFAULT_TOOL_TIMEOUT`
- **Flexible guidance**: "3-4 minutes" to accommodate configuration changes

## Verification and Testing

### Test Suite Created

**`test_system_prompt_enhancements.py`** provides comprehensive verification:

1. **Template Loading Test**
   - Verifies prompt factory can load templates
   - Confirms template file exists and contains guidelines

2. **System Prompt Generation Test**
   - Tests full prompt creation with context and modes
   - Verifies all key phrases are present
   - Shows sample of guidelines section

3. **Content Verification**
   - Checks for all critical guideline elements
   - Validates proper integration with existing prompt structure

### Test Results

✅ **All tests pass** - Guidelines successfully integrated

✅ **Full coverage** - All key phrases and concepts included

✅ **Proper integration** - Works with existing context and mode system

## Usage Impact

### For AI Agents

Agents now receive explicit guidance about:
- **Appropriate waiting periods** for tool execution
- **Normal vs. abnormal timeout scenarios**
- **When and how to retry** operations
- **Communication vs. execution failures**

### For Users

- **Reduced false timeouts** and duplicate operations
- **Better agent patience** with long-running tools
- **Improved reliability** of complex operations
- **More informative communication** about delays

## Configuration Integration

### Current Timeout Settings

- **`serena_config.yml`**: `tool_timeout: 180` (3 minutes)
- **Default system**: `DEFAULT_TOOL_TIMEOUT = 240` (4 minutes)
- **AsyncToolExecutor**: Configurable retry logic with exponential backoff

### Dynamic Configuration

The prompt guidelines can be made dynamic by:
1. Reading timeout values from configuration
2. Injecting values into prompt template using Jinja2 variables
3. Updating guidelines text based on actual system settings

Example enhancement:
```yaml
### Tool Execution Guidelines
Normal timeout period is {{ timeout_minutes }} minutes...
```

## Best Practices Implemented

### Prompt Engineering

1. **Clear Structure**: Dedicated section with prominent heading
2. **Imperative Language**: Strong verbs ("Wait", "Avoid", "Trust")
3. **Specific Numbers**: "3-4 minutes" vs. vague "some time"
4. **Explanation Context**: Why delays occur and what they mean
5. **Action Items**: Specific steps when timeouts occur

### Agent Behavior

1. **Patience First**: Wait before assuming failure
2. **Verification Second**: Check for partial results
3. **Retry Last**: Only after confirmed failure
4. **Communication**: Inform users about delays

## Future Enhancements

### Potential Improvements

1. **Dynamic Timeout Values**: Inject actual configuration into prompt
2. **Tool-Specific Guidance**: Different timeouts for different tool types
3. **Load-Based Adaptation**: Adjust expectations based on system load
4. **Progress Indicators**: Guidelines for long-running operation feedback

### Monitoring and Metrics

1. **Timeout Reduction**: Track decrease in false timeouts
2. **Retry Frequency**: Monitor intelligent retry behavior
3. **User Satisfaction**: Measure improved reliability perception
4. **Communication Quality**: Better agent explanations of delays

## Conclusion

The enhanced system prompt provides AI agents with comprehensive guidance about tool call reliability and timing expectations. This should significantly reduce communication-related issues and improve the overall user experience with Serena's MCP server.

The implementation is:
- ✅ **Non-invasive**: Works with existing architecture
- ✅ **Configurable**: Can be updated as needed
- ✅ **Testable**: Comprehensive verification suite
- ✅ **Maintainable**: Clear documentation and structure

The enhancements address the root cause of communication reliability issues by educating agents about the asynchronous nature of the system and proper timeout handling behavior.
