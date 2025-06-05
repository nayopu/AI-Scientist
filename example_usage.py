#!/usr/bin/env python3
"""
Example usage of the unified LLM client system.

This script demonstrates how to use the new environment variable-based
LLM configuration instead of hardcoded client creation.
"""

import os
from llm_client import get_llm_client, get_response_from_llm

def main():
    print("=== Unified LLM Client Example ===\n")
    
    # Check if AI_SCIENTIST_MODEL is set
    model_config = os.environ.get("AI_SCIENTIST_MODEL")
    if not model_config:
        print("❌ AI_SCIENTIST_MODEL environment variable not set!")
        print("\nTo use this example, set the environment variable:")
        print("export AI_SCIENTIST_MODEL='provider:model_name'")
        print("\nExamples:")
        print("  export AI_SCIENTIST_MODEL='openai:gpt-4o-mini'")
        print("  export AI_SCIENTIST_MODEL='anthropic:claude-3-5-sonnet-20241022'")
        print("  export AI_SCIENTIST_MODEL='openrouter:llama3.1-405b'")
        print("\nAlso remember to set the appropriate API key:")
        print("  export OPENAI_API_KEY='your-key'")
        print("  export ANTHROPIC_API_KEY='your-key'")
        print("  export OPENROUTER_API_KEY='your-key'")
        return
    
    print(f"✓ Using model configuration: {model_config}")
    
    try:
        # Get the configured client - no parameters needed!
        client, model_name = get_llm_client()
        print(f"✓ Client created successfully for model: {model_name}")
        
        # Example of making a request (will fail without valid API key, but shows the interface)
        print("\n--- Example API Usage ---")
        try:
            response, history = get_response_from_llm(
                msg="Hello! Can you tell me what model you are?",
                system_message="You are a helpful assistant.",
                client=client,
                model=model_name
            )
            print(f"✓ Response: {response[:100]}...")
            
        except Exception as e:
            print(f"⚠️  API call failed (likely missing/invalid API key): {e}")
            print("   This is expected if you haven't set a valid API key.")
            
    except Exception as e:
        print(f"❌ Failed to create client: {e}")
        print("\nCommon fixes:")
        print("1. Check AI_SCIENTIST_MODEL format: 'provider:model_name'")
        print("2. Set the appropriate API key environment variable")
        print("3. Ensure the LLM client package is installed: pip install -e .")

if __name__ == "__main__":
    main() 