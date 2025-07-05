#!/usr/bin/env python3
"""
Test script to verify that the enhanced system prompt with tool execution guidelines is working correctly.
"""

import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from serena.prompt_factory import SerenaPromptFactory
from serena.config import SerenaAgentContext, SerenaAgentMode

def test_system_prompt():
    """Test that the system prompt includes the new tool execution guidelines."""
    print("Testing enhanced system prompt...")
    
    # Create prompt factory
    prompt_factory = SerenaPromptFactory()
    
    # Load default context and modes
    try:
        context = SerenaAgentContext.load_default()
        modes = SerenaAgentMode.load_default_modes()
        
        print(f"✓ Loaded context: {context.name}")
        print(f"✓ Loaded modes: {[mode.name for mode in modes]}")
        
    except Exception as e:
        print(f"✗ Failed to load context/modes: {e}")
        return False
    
    # Create system prompt
    try:
        system_prompt = prompt_factory.create_system_prompt(
            context_system_prompt=context.prompt,
            mode_system_prompts=[mode.prompt for mode in modes],
        )
        
        print(f"✓ System prompt created (length: {len(system_prompt)} chars)")
        
    except Exception as e:
        print(f"✗ Failed to create system prompt: {e}")
        return False
    
    # Check for our enhancements
    checks = [
        ("Tool Execution Guidelines", "Tool Execution Guidelines - IMPORTANT"),
        ("Wait patiently", "Wait patiently for tool results"),
        ("Normal timeout period", "Normal timeout period is 3-4 minutes"),
        ("Avoid duplicate tool calls", "Avoid duplicate tool calls"),
        ("Trust the process", "Trust the process"),
        ("Infrastructure retry logic", "The infrastructure has built-in retry logic"),
    ]
    
    print("\nChecking for enhanced guidelines:")
    all_found = True
    
    for check_name, check_text in checks:
        if check_text in system_prompt:
            print(f"✓ Found: {check_name}")
        else:
            print(f"✗ Missing: {check_name}")
            all_found = False
    
    # Print a sample of the relevant section
    if "Tool Execution Guidelines" in system_prompt:
        start_idx = system_prompt.find("### Tool Execution Guidelines")
        end_idx = system_prompt.find("### Code Reading", start_idx)
        if end_idx == -1:
            end_idx = start_idx + 1000  # Show first 1000 chars if no end marker
        
        sample = system_prompt[start_idx:end_idx].strip()
        print(f"\nTool Execution Guidelines section:")
        print("-" * 50)
        print(sample)
        print("-" * 50)
    
    return all_found

def test_prompt_factory_loading():
    """Test that the prompt factory can load templates correctly."""
    print("\nTesting prompt factory loading...")
    
    try:
        prompt_factory = SerenaPromptFactory()
        print("✓ SerenaPromptFactory created successfully")
        
        # Test if we can access the template directory
        from serena.constants import PROMPT_TEMPLATES_DIR
        print(f"✓ Template directory: {PROMPT_TEMPLATES_DIR}")
        
        template_path = Path(PROMPT_TEMPLATES_DIR) / "system_prompt.yml"
        if template_path.exists():
            print(f"✓ System prompt template exists: {template_path}")
            
            # Check the template content
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            if "Tool Execution Guidelines" in template_content:
                print("✓ Template contains enhanced guidelines")
            else:
                print("✗ Template missing enhanced guidelines")
                return False
                
        else:
            print(f"✗ System prompt template not found: {template_path}")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Prompt factory loading failed: {e}")
        return False

def main():
    """Main test function."""
    print("=" * 60)
    print("Enhanced System Prompt Verification Test")
    print("=" * 60)
    
    # Test 1: Template loading
    template_test = test_prompt_factory_loading()
    
    # Test 2: System prompt generation
    prompt_test = test_system_prompt()
    
    print("\n" + "=" * 60)
    print("TEST RESULTS:")
    print("=" * 60)
    
    if template_test and prompt_test:
        print("✅ ALL TESTS PASSED")
        print("✓ Template contains enhanced guidelines")
        print("✓ System prompt correctly includes tool execution guidance")
        print("\nThe enhanced prompt system is working correctly!")
    else:
        print("❌ SOME TESTS FAILED")
        if not template_test:
            print("✗ Template loading issues")
        if not prompt_test:
            print("✗ System prompt generation issues")
        print("\nPlease check the configuration and try again.")

if __name__ == "__main__":
    main()
