from setuptools import setup, find_packages

setup(
    name="llm-client",
    version="1.0.0",
    description="Unified LLM client for AI Scientist project",
    author="AI Scientist Team", 
    packages=find_packages(),
    install_requires=[
        "anthropic>=0.25.0",
        "openai>=1.0.0",
        "google-generativeai>=0.3.0",
        "backoff>=2.0.0",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9", 
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
) 