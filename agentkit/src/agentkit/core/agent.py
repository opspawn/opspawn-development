# agentkit/agentkit/core/agent.py
"""Core Agent class definition for agentkit."""

import asyncio
from typing import Any, Dict, List, Optional

import logging # Add logging import
import asyncio
from typing import Any, Dict, List, Optional

# Interface Imports (Relative)
from .interfaces import (
    BaseLongTermMemory, # Add LTM interface import
    BaseMemory,
    BasePlanner,
    BaseSecurityManager,
    BaseToolManager,
)
from .interfaces.planner import Plan, PlanStep

# Concrete Implementation Imports (Relative)
from ..memory.short_term import ShortTermMemory
from ..planning.simple_planner import SimplePlanner
from ..tools.registry import ToolRegistry, ToolNotFoundError
from ..tools.schemas import ToolResult

# Placeholder Security Manager (if needed for default)
# Placeholder Security Manager
class PlaceholderSecurityManager(BaseSecurityManager):
    """A default, permissive security manager."""
    async def check_permissions(self, action: str, context: Dict[str, Any]) -> bool:
        print(f"Security Check (Placeholder): Allowing action '{action}'")
        # logger.debug(f"Security Check (Placeholder): Allowing action '{action}'") # Use logger later
        return True

logger = logging.getLogger(__name__) # Setup logger

class Agent:
    """
    The core agent class responsible for coordinating planning, memory, and execution.
    Uses dependency injection for core components based on defined interfaces.
    """

    def __init__(
        self,
        planner: Optional[BasePlanner] = None,
        memory: Optional[BaseMemory] = None,
        long_term_memory: Optional[BaseLongTermMemory] = None, # Add LTM parameter
        tool_manager: Optional[BaseToolManager] = None,
        security_manager: Optional[BaseSecurityManager] = None,
        profile: Optional[Dict[str, Any]] = None,
    ):
        """
        Initializes the Agent.

        Args:
            planner: An instance implementing BasePlanner. Defaults to SimplePlanner.
            memory: An instance implementing BaseMemory (short-term). Defaults to ShortTermMemory.
            long_term_memory: An instance implementing BaseLongTermMemory. Defaults to None.
            tool_manager: An instance implementing BaseToolManager. Defaults to ToolRegistry.
            security_manager: An instance implementing BaseSecurityManager. Defaults to PlaceholderSecurityManager.
            profile: A dictionary containing agent configuration, persona, etc. Defaults to an empty dict.

        Raises:
            TypeError: If any dependency is not an instance of its corresponding base class.
        """
        # Assign defaults first (including LTM)
        _planner = planner if planner is not None else SimplePlanner()
        _memory = memory if memory is not None else ShortTermMemory()
        _long_term_memory = long_term_memory # Default is None
        _tool_manager = tool_manager if tool_manager is not None else ToolRegistry()
        _security_manager = security_manager if security_manager is not None else PlaceholderSecurityManager()
        _profile = profile if profile is not None else {}

        # Validate types before assigning to self (including LTM)
        if not isinstance(_planner, BasePlanner):
            raise TypeError("planner must be an instance of BasePlanner")
        if not isinstance(_memory, BaseMemory):
            raise TypeError("memory must be an instance of BaseMemory")
        if _long_term_memory is not None and not isinstance(_long_term_memory, BaseLongTermMemory):
             raise TypeError("long_term_memory must be an instance of BaseLongTermMemory or None")
        if not isinstance(_tool_manager, BaseToolManager):
            raise TypeError("tool_manager must be an instance of BaseToolManager")
        if not isinstance(_security_manager, BaseSecurityManager):
            raise TypeError("security_manager must be an instance of BaseSecurityManager")

        self.planner: BasePlanner = _planner
        self.memory: BaseMemory = _memory # Short-term memory
        self.long_term_memory: Optional[BaseLongTermMemory] = _long_term_memory
        self.tool_manager: BaseToolManager = _tool_manager
        self.security_manager: BaseSecurityManager = _security_manager
        self.profile: Dict[str, Any] = _profile

        # Attempt to get tool count if the tool_manager is a ToolRegistry (common case)
        tool_count = "N/A"
        if isinstance(self.tool_manager, ToolRegistry):
             tool_count = len(self.tool_manager.list_tools())

        ltm_type = type(self.long_term_memory).__name__ if self.long_term_memory else "None"
        logger.info(
            f"Agent initialized with Planner: {type(self.planner).__name__}, "
            f"Memory (ST): {type(self.memory).__name__}, "
            f"Memory (LT): {ltm_type}, "
            f"ToolManager: {type(self.tool_manager).__name__} ({tool_count} tools), "
            f"SecurityManager: {type(self.security_manager).__name__}"
        )

    async def _get_context(self) -> Dict[str, Any]:
        """
        Constructs the context for the planner based on memory, profile, and available tools.
        """
        tool_specs = []
        # Check if the tool_manager has list_tools (like ToolRegistry)
        if isinstance(self.tool_manager, ToolRegistry):
             # Reason: Safely access list_tools only if available on the concrete type.
             tool_specs = [spec.model_dump() for spec in self.tool_manager.list_tools()]

        # Retrieve short-term context asynchronously from memory
        messages = await self.memory.get_context()

        context = {
            "messages": messages,
            "profile": self.profile,
            "available_tools": tool_specs,
        }

        return context

    def run(self, goal: str) -> Any:
        """Synchronous wrapper for the main async execution loop."""
        # Ensure execution happens in an async context
        return asyncio.run(self.run_async(goal))

    async def run_async(self, goal: str) -> Any:
        """
        Asynchronous execution loop for a given task or goal.

        Args:
            goal: The objective to achieve.

        Returns:
            The final result of the task execution.
        """
        logger.info(f"Agent starting task: {goal}")
        await self.memory.add_message(role="user", content=goal)

        # 1. Retrieve Long-Term Memories (if available)
        retrieved_memories_text = ""
        if self.long_term_memory:
            try:
                # Use goal as the initial query for LTM
                retrieved_tuples = await self.long_term_memory.search_memory(query=goal, n_results=3)
                if retrieved_tuples:
                    formatted_memories = [f"- {mem[0]} (Score: {mem[1]:.4f})" for mem in retrieved_tuples]
                    retrieved_memories_text = "Relevant information from past tasks:\n" + "\n".join(formatted_memories)
                    logger.info(f"Retrieved {len(retrieved_tuples)} long-term memories.")
                    # Optionally add retrieved memories to short-term context? For now, pass directly to planner.
                    # await self.memory.add_message(role="system", content=retrieved_memories_text)
            except Exception as e:
                logger.error(f"Failed to search long-term memory: {e}", exc_info=True)
                # Continue execution even if LTM search fails

        # 2. Get Short-Term Context
        context = await self._get_context()
        logger.info(f"Context prepared with {len(context.get('messages', []))} messages.")

        # Add retrieved LTM to context for planner
        context["retrieved_memories"] = retrieved_memories_text # Add even if empty

        # 3. Generate plan
        try:
            plan_obj: Plan = await self.planner.plan(goal=goal, context=context) # Pass context with LTM
            logger.info(f"Plan generated with {len(plan_obj.steps)} steps.")
        except Exception as e:
            # Handle planner errors
            error_msg = f"Planning failed: {e}"
            logger.error(error_msg, exc_info=True)
            await self.memory.add_message(role="assistant", content=error_msg)
            # Also add failure to LTM? Maybe not for planning failures.
            return error_msg # Return error immediately

        # Handle empty plan
        if not plan_obj or not plan_obj.steps: # Check the steps list within the Plan object
            empty_plan_msg = "Planner returned an empty plan. Task cannot proceed."
            logger.warning(f"    - {empty_plan_msg}")
            await self.memory.add_message(role="assistant", content=empty_plan_msg)
            # Add empty plan outcome to LTM? Maybe not.
            return empty_plan_msg

        # 4. Execute plan steps
        logger.info("Executing plan:")
        final_result: Any = None
        step_results: List[Any] = []  # Store results of each step if needed

        for i, step in enumerate(plan_obj.steps): # Iterate through plan_obj.steps
            # Convert PlanStep back to dict for logging/context if needed, or use attributes directly
            step_dict = step.model_dump() # Use Pydantic's model_dump for dict representation
            logger.info(f"  - Executing Step {i + 1}: {step_dict}")

            # Security Check (Placeholder) - Use step attributes directly
            action_type = step.action_type # Use attribute
            action_desc = action_type
            if action_type == 'tool_call':
                # Access tool_name within details attribute
                tool_name = step.details.get('tool_name', '')
                action_desc = f"{action_type}:{tool_name}"

            # Pass the PlanStep object directly to check_permissions context
            if not await self.security_manager.check_permissions(action=action_desc, context={"step": step}):
                permission_error_msg = f"Permission denied for action '{action_desc}'."
                logger.warning(f"    - Step failed: {permission_error_msg}")
                final_result = f"Task failed at step {i + 1}: {permission_error_msg}"
                # Use the specific error message for memory
                await self.memory.add_message(role="assistant", content=f"Step {i+1} outcome: {permission_error_msg}")
                break # Stop execution on permission denial

            step_outcome = await self._execute_step(step) # Pass the PlanStep object
            step_results.append(step_outcome)  # Store outcome (e.g., ToolResult)

            # Update memory after each step
            # Refined memory update logic
            if isinstance(step_outcome, ToolResult):
                memory_content = f"Tool '{step_outcome.tool_name}' called with args {step_outcome.tool_args}. "
                if step_outcome.error:
                    memory_content += f"Failed: {step_outcome.error}"
                else:
                    memory_content += f"Result: {step_outcome.output}"
                await self.memory.add_message(role="tool", content=memory_content, metadata={"tool_result": step_outcome.model_dump()})
            else:
                # Handle non-tool results (e.g., completion message)
                 # Add outcome for non-tool steps (like log, or unknown placeholder)
                 await self.memory.add_message(role="assistant", content=f"Step {i+1} outcome: {step_outcome}")


            # Check if the step resulted in an error or completion
            step_failed = False
            if isinstance(step_outcome, ToolResult) and step_outcome.error:
                logger.warning(f"    - Step failed (Tool Error): {step_outcome.error}")
                final_result = f"Task failed at step {i + 1}: {step_outcome.error}"
                step_failed = True
                # Memory already updated above
            elif isinstance(step_outcome, str) and step_outcome.startswith("Unknown action type:"):
                 # Handle unknown action error specifically if needed, though memory is updated above
                 logger.warning(f"    - Step failed (Unknown Action): {step_outcome}")
                 final_result = f"Task failed at step {i + 1}: {step_outcome}"
                 step_failed = True
                 # Memory already updated above

            if step_failed:
                 break # Stop execution on error

            # Check for completion *after* checking for errors - Use step attributes
            if step.action_type == "final_answer": # Check action_type
                final_result = step.details.get("answer", "Task completed successfully.") # Get answer from details
                logger.info(f"    - Task marked complete (Final Answer).")
                # Memory already updated above with the final answer as step_outcome
                break  # Stop execution on completion

        # If loop finished *and* no final_result was set by break (error/completion)
        if final_result is None:
            no_completion_msg = "Plan executed but no explicit completion step found."
            logger.warning(f"    - {no_completion_msg}")
            # Only add this message if the loop finished normally
            await self.memory.add_message(role="assistant", content=f"Final Result: {no_completion_msg}")
            final_result = no_completion_msg # Set the final result

        # 5. Add final result to Long-Term Memory (if available)
        if self.long_term_memory:
            try:
                # Create a summary memory text
                memory_text_to_add = f"Goal: {goal}\nFinal Result: {final_result}"
                await self.long_term_memory.add_memory(
                    text=memory_text_to_add,
                    metadata={"goal": goal, "status": "completed" if not any(isinstance(r, ToolResult) and r.error for r in step_results) else "failed"}
                )
                logger.info("Added final result to long-term memory.")
            except Exception as e:
                logger.error(f"Failed to add final result to long-term memory: {e}", exc_info=True)
                # Continue even if LTM add fails

        # Log final memory state size
        current_context = await self.memory.get_context()
        logger.info(f"Task finished. Final message count: {len(current_context)}")

        return final_result

    async def _execute_step(self, step: PlanStep) -> Any: # Accept PlanStep object
        """Executes a single step from the plan using the appropriate manager."""
        action_type = step.action_type # Use attribute
        details = step.details # Use attribute

        if action_type == "tool_call":
            tool_name = details.get("tool_name") # Get from details
            tool_args = details.get("arguments", {}) # Get from details
            if not tool_name:
                # Reason: Ensure tool_name is provided for tool calls.
                logger.error("Missing 'tool_name' in tool_call step details.")
                return ToolResult(tool_name="unknown", tool_args=tool_args, error="Missing 'tool_name' in tool_call args.", status_code=400)

            logger.info(f"    - Calling tool manager to execute: {tool_name} with args: {tool_args}")
            # Delegate execution to the tool manager
            result: ToolResult = await self.tool_manager.execute_tool(tool_name, tool_args)

            if result.error:
                logger.warning(f"    - Tool execution failed (reported by manager): {result.error}")
            else:
                logger.info(f"    - Tool execution successful (reported by manager). Output: {result.output}")
            return result # Return the result directly from the manager

        elif action_type == "final_answer":
            # No specific execution, just return the answer from details
            logger.info("    - Final answer step reached.")
            return details.get("answer", "Final answer step executed.")
        elif action_type == "error":
             # Handle error step type if planner returns it
             error_message = details.get("message", "Error step executed.")
             logger.error(f"    - Error Step: {error_message}")
             return f"Error action executed: {error_message}"
        else:
            # Handle unknown actions by returning an error message
            # This case might be less likely now with Literal type hint
            unknown_action_msg = f"Unknown action type: '{action_type}'."
            logger.error(f"    - {unknown_action_msg}")
            return unknown_action_msg # Return the error message as the outcome
