from setuptools import setup

setup(
    name="cortex",
    version="1.0.0",
    description="Strategic orchestrator - What should I do next?",
    author="Jesse Kemp",
    python_requires=">=3.8",
    packages=["cortex"],
    package_dir={"cortex": "."},
    install_requires=[],  # Core has no deps
    extras_require={
        "learning": [
            "fastapi>=0.104.0",
            "uvicorn>=0.24.0",
            "apscheduler>=3.10.0",
            "structlog>=23.2.0",
            "pydantic>=2.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cortex=cli:main",
        ],
    },
)
