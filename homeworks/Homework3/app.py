"""Command-line Gemini agent with a Terminal tool and session chat history."""

import platform
import sys

from langchain.agents import create_agent
from langchain_community.agent_toolkits.load_tools import load_tools
from langchain_core.callbacks import BaseCallbackHandler
from langchain_google_genai import ChatGoogleGenerativeAI

from config import required_env
from rag import create_security_knowledge_tool


class TerminalDisplayHandler(BaseCallbackHandler):
    """Show Terminal and security knowledge tool activity in the CLI."""

    def on_tool_start(self, serialized, input_str: str, **kwargs) -> None:
        """Print the tool name and arguments before execution."""
        name = (serialized or {}).get("name", "terminal")
        print(f"\nTool call: {name}\nArguments: {input_str}", flush=True)

    def on_tool_end(self, output, **kwargs) -> None:
        """Print the tool's returned content after execution."""
        content = getattr(output, "content", output)
        print(f"Tool result:\n{content}\n", flush=True)

    def on_tool_error(self, error: BaseException, **kwargs) -> None:
        """Make a failed tool execution visible in the CLI."""
        print(f"Tool error: {error}", file=sys.stderr, flush=True)


def build_agent():
    """Build a Gemini agent with Terminal and local security knowledge tools."""
    model = ChatGoogleGenerativeAI(
        model=required_env("GOOGLE_MODEL"),
        google_api_key=required_env("GOOGLE_API_KEY"),
        vertexai=False,
    )
    return create_agent(
        model=model,
        tools=[
            *load_tools(["terminal"], allow_dangerous_tools=True),
            create_security_knowledge_tool(model),
        ],
        system_prompt=(
            "You are a helpful conversational assistant. Use Terminal when "
            "shell commands are needed to fulfill the user's request. "
            "Use security_knowledge for questions about the locally indexed "
            "security documents, course notes, and course-specific procedures. "
            "If that tool reports missing documents or insufficient evidence, "
            "tell the user rather than inventing a course-specific answer. "
            f"The operating system is {platform.system()}. "
            "Explain results clearly."
        ),
    )


def chat_loop(agent) -> None:
    """Read requests until exit, quit, EOF, or an interrupt, retaining history."""
    messages = []
    tool_display = TerminalDisplayHandler()
    print("Homework 3 Gemini agent. Type exit or quit to stop.")
    while True:
        try:
            request = input("You: ").strip()
            if request.lower() in {"exit", "quit"}:
                break
            if not request:
                continue
            result = agent.invoke(
                {"messages": [*messages, {"role": "user", "content": request}]},
                config={"callbacks": [tool_display]},
            )
            messages = result["messages"]
            print(f"Agent: {messages[-1].text}")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        except Exception as exc:
            print(f"Agent error: {exc}", file=sys.stderr)


def main() -> None:
    """Initialize the configured agent and start the interactive CLI."""
    try:
        agent = build_agent()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    chat_loop(agent)


if __name__ == "__main__":
    main()
