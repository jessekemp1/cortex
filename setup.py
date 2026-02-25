from pathlib import Path

from setuptools import find_packages, setup

long_description = ""
readme = Path(__file__).parent / "README.md"
if readme.exists():
    long_description = readme.read_text(encoding="utf-8")

setup(
    name="cortex-intelligence",
    version="1.0.0",
    description="Persistent cross-session intelligence layer for LLM agents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Jesse Kemp",
    url="https://github.com/jessekemp1/cortex",
    license="Apache-2.0",
    python_requires=">=3.11",
    packages=find_packages(
        exclude=[
            "tests*",
            "docs*",
            "examples*",
            "reports*",
            "analysis*",
            "scripts*",
            "MARKETING*",
            "FUTURE*",
            "STRATEGY*",
            "OPUS*",
            "GPT5*",
            "_dead*",
            "_archive*",
            "mvp*",
            "cortex_mvp*",
            "golden-spec-method*",
            "config-backups*",
            "vision*",
            "site*",
            "dashboard*",
            "batch*",
            "automation*",
            "v2*",
            "v21*",
        ]
    ),
    include_package_data=True,
    install_requires=[
        "anthropic>=0.40.0",
        "rich>=13.0.0",
        "pydantic>=2.5.0",
        "requests>=2.31.0",
        "PyYAML>=6.0.1",
        "structlog>=23.2.0",
        "python-dotenv>=1.0.0",
        "psutil>=5.9.0",
        "pytz>=2024.1",
        "setuptools>=75.6.0",
    ],
    extras_require={
        "server": [
            "fastapi>=0.104.0",
            "uvicorn>=0.24.0",
            "apscheduler>=3.10.0",
            "slowapi>=0.1.9",
        ],
        "analytics": [
            "xgboost>=2.0.0",
            "shap>=0.44.0",
            "openai>=1.0.0",
        ],
        "all": [
            "fastapi>=0.104.0",
            "uvicorn>=0.24.0",
            "apscheduler>=3.10.0",
            "slowapi>=0.1.9",
            "xgboost>=2.0.0",
            "shap>=0.44.0",
            "openai>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cortex=cortex.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
