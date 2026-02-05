"""Edit validation middleware.

Validates edit_file tool calls before execution to prevent no-op edits
where old_string equals new_string.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command


class EditValidationMiddleware(AgentMiddleware[Any, Any]):
    """Middleware that validates edit_file tool calls.

    Rejects no-op edits where old_string equals new_string to prevent
    unnecessary human-in-the-loop interrupts for empty changes.
    """

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Validate edit_file calls before execution.

        Args:
            request: The tool call request being processed.
            handler: The handler function to call with the request.

        Returns:
            Error message if validation fails, otherwise the handler result.
        """
        tool_call = request.tool_call
        if tool_call["name"] == "edit_file":
            args = tool_call.get("args", {})
            old_string = args.get("old_string", "")
            new_string = args.get("new_string", "")

            if old_string == new_string:
                return ToolMessage(
                    content=(
                        "Error: No-op edit rejected. "
                        "old_string and new_string are identical. "
                        "Please provide a different new_string that actually modifies the content."
                    ),
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"],
                    status="error",
                )

        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """Async version of wrap_tool_call.

        Args:
            request: The tool call request being processed.
            handler: The async handler function to call with the request.

        Returns:
            Error message if validation fails, otherwise the handler result.
        """
        tool_call = request.tool_call
        if tool_call["name"] == "edit_file":
            args = tool_call.get("args", {})
            old_string = args.get("old_string", "")
            new_string = args.get("new_string", "")

            if old_string == new_string:
                return ToolMessage(
                    content=(
                        "Error: No-op edit rejected. "
                        "old_string and new_string are identical. "
                        "Please provide a different new_string that actually modifies the content."
                    ),
                    tool_call_id=tool_call["id"],
                    name=tool_call["name"],
                    status="error",
                )

        return await handler(request)
