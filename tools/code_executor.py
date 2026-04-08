"""LangChain tool that runs Python code in a Daytona sandbox and returns stdout."""
from langchain_core.tools import tool
from sandbox.executor import run_code


@tool
def code_executor(code: str) -> str:
    """Execute Python code in an isolated Daytona sandbox and return the output.

    Use this tool when you need to perform data analysis, numerical computation,
    generate plots, or run any arbitrary Python code safely.

    Args:
        code: Valid Python source code to execute.

    Returns:
        stdout output from the code execution, or an error message.
    """
    result = run_code(code)
    if result["exit_code"] != 0 and result["stderr"]:
        return f"ERROR (exit {result['exit_code']}):\n{result['stderr']}\n\nstdout:\n{result['stdout']}"
    return result["stdout"] or "(no output)"
