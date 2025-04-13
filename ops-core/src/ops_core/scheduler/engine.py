"""
In-memory implementation of the task scheduling engine for Ops Core.

This provides a basic, non-persistent scheduler suitable for development
and testing. It interacts with a metadata store to manage task states.
"""

import asyncio
import logging
import traceback # Import traceback for detailed error logging
import traceback # Import traceback for detailed error logging
import os
import uuid
from typing import Any, Dict, Optional

# Agentkit imports
from agentkit.core.agent import Agent
from agentkit.memory.short_term import ShortTermMemory
from agentkit.memory.long_term.chroma_memory import ChromaLongTermMemory # Import Chroma LTM
from agentkit.planning.placeholder_planner import PlaceholderPlanner # Default/fallback
from agentkit.planning.react_planner import ReActPlanner # Import ReAct
from agentkit.core.interfaces import ( # Group imports
    BaseSecurityManager,
    BasePlanner,
    BaseLlmClient,
    BaseLongTermMemory, # Import LTM interface
)
from agentkit.tools.registry import ToolRegistry
# LLM Client imports (add others as needed)
from agentkit.llm_clients.openai_client import OpenAiClient
from agentkit.llm_clients.anthropic_client import AnthropicClient
from agentkit.llm_clients.google_client import GoogleClient
from agentkit.llm_clients.openrouter_client import OpenRouterClient

# Ops-core imports
import dramatiq # Import dramatiq itself
from ops_core.models.tasks import Task, TaskStatus # Corrected path and removed duplicate
from ops_core.metadata.base import BaseMetadataStore # Corrected path
from ops_core.metadata.sql_store import SqlMetadataStore # Corrected path
from ops_core.metadata.store import TaskNotFoundError # Corrected path
from ops_core.mcp_client.client import OpsMcpClient # Corrected path
from ops_core.mcp_client.proxy_tool import MCPProxyTool # Corrected path
# Import session factory and session type for actor
from ops_core.dependencies import async_session_factory, get_mcp_client # Corrected path
from sqlalchemy.ext.asyncio import AsyncSession
# Removed get_metadata_store as actor will create its own
# Removed direct broker import: from ops_core.tasks.broker import broker

logger = logging.getLogger(__name__)

# Default Security Manager (replace with actual implementation if needed)
class DefaultSecurityManager(BaseSecurityManager):
    def check_execution(self, action_type: str, details: Dict[str, Any]) -> bool:
        logger.debug(f"Security check for action '{action_type}': Allowing.")
        return True

    # Implement the method matching the BaseSecurityManager interface
    async def check_permissions(self, action: str, context: Dict[str, Any]) -> bool:
        """Check permissions based on action and context."""
        # For now, maintain permissive behavior but log the received action/context
        logger.debug(f"Security Check: Action='{action}', Context Keys='{list(context.keys())}'. Allowing by default.")
        return True

# --- LLM/Planner Instantiation Logic ---

def get_llm_client() -> BaseLlmClient:
    """Instantiates the appropriate LLM client based on environment variables."""
    provider = os.getenv("AGENTKIT_LLM_PROVIDER", "openai").lower() # Default to openai
    # Add API key checks if needed, or assume they are handled by the client itself via env vars
    # api_key = os.getenv(f"{provider.upper()}_API_KEY")
    # if not api_key:
    #     raise ValueError(f"{provider.upper()}_API_KEY environment variable not set.")

    logger.info(f"Instantiating LLM client for provider: {provider}")
    if provider == "openai":
        return OpenAiClient()
    elif provider == "anthropic":
        return AnthropicClient()
    elif provider == "google":
        return GoogleClient()
    elif provider == "openrouter":
        return OpenRouterClient()
    else:
        logger.error(f"Unsupported LLM provider specified: {provider}. Falling back to Google.")
        # Fallback or raise error - let's fallback to the new default
        return GoogleClient()

def get_long_term_memory() -> Optional[BaseLongTermMemory]:
    """Instantiates the appropriate long-term memory client based on environment variables."""
    provider = os.getenv("AGENTKIT_LTM_PROVIDER", "none").lower()
    logger.info(f"Checking long-term memory provider: {provider}")

    if provider == "chroma":
        persist_directory = os.getenv("AGENTKIT_LTM_CHROMA_PATH", "./.chroma_db")
        collection_name = os.getenv("AGENTKIT_LTM_CHROMA_COLLECTION", "agent_memory")
        logger.info(f"Instantiating ChromaDB LTM: path='{persist_directory}', collection='{collection_name}'")
        try:
            return ChromaLongTermMemory(
                persist_directory=persist_directory,
                collection_name=collection_name
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB LTM: {e}", exc_info=True)
            return None # Fail gracefully if LTM init fails
    elif provider == "none":
        logger.info("Long-term memory is disabled (AGENTKIT_LTM_PROVIDER=none).")
        return None
    else:
        logger.warning(f"Unsupported LTM provider specified: {provider}. Disabling LTM.")
        return None

def get_planner(llm_client: BaseLlmClient) -> BasePlanner:
    """Instantiates the appropriate planner, injecting the LLM client."""
    planner_type = os.getenv("AGENTKIT_PLANNER_TYPE", "react").lower()
    model_name = os.getenv("AGENTKIT_LLM_MODEL") # Model might be needed by planner

    logger.info(f"Instantiating planner of type: {planner_type}")
    if planner_type == "react":
        # ReActPlanner only takes the llm_client
        return ReActPlanner(llm_client=llm_client)
    elif planner_type == "placeholder":
        return PlaceholderPlanner()
    else:
        logger.error(f"Unsupported planner type specified: {planner_type}. Falling back to ReAct.")
        # Fallback or raise error
        return ReActPlanner(llm_client=llm_client)


# --- Scheduler Implementation ---

class InMemoryScheduler:
    """
    Basic in-memory task scheduler.

    Uses Dramatiq to dispatch agent tasks for asynchronous execution.
    """
    # Accept mcp_client for test compatibility, even if not directly used here
    # Update type hint to accept any BaseMetadataStore implementation
    def __init__(self, metadata_store: BaseMetadataStore, mcp_client: Optional[OpsMcpClient] = None):
        self.metadata_store = metadata_store
        # self.mcp_client = mcp_client # Store if needed, but actor uses get_mcp_client()
        logger.info("InMemoryScheduler initialized.")
        # No background task loop needed as Dramatiq handles execution

    async def submit_task(self, name: str, task_type: str, input_data: Dict[str, Any]) -> Task:
        """
        Submits a new task to the system.

        Adds the task to the metadata store and dispatches agent tasks
        to the Dramatiq broker.
        """
        task_id = f"task_{uuid.uuid4()}"
        new_task = Task(
            task_id=task_id,
            name=name,
            task_type=task_type,
            input_data=input_data,
            status=TaskStatus.PENDING,
            # created_at/updated_at handled by Pydantic default_factory
        )
        logger.info(f"Scheduler submit_task: Submitting task {task_id} ({name}, type: {task_type})")
        # Capture the potentially refreshed task object returned by add_task
        logger.info(f"Scheduler submit_task: Calling metadata_store.add_task for {task_id}...")
        persisted_task = await self.metadata_store.add_task(new_task)
        logger.info(f"Scheduler submit_task: metadata_store.add_task returned for {task_id}. Persisted task status: {persisted_task.status}")

        # Dispatch agent tasks to the broker
        # Check if it's an agent task that needs dispatching
        if task_type == "agent_task": # Changed from "agent_run" to "agent_task"
            # Extract goal from input_data, provide a default if missing
            goal = input_data.get("prompt", input_data.get("goal", "No goal or prompt specified"))
            logger.info(f"Dispatching agent task {task_id} to broker with goal: '{goal}'")
            # Send message to the actor
            logger.info(f"Scheduler submit_task: Sending task {task_id} to Dramatiq actor...")
            # Ensure the actor is imported correctly at the top of the file
            # Actor is defined in this file, no import needed here
            execute_agent_task_actor.send(task_id=task_id, goal=goal, input_data=input_data)
            logger.info(f"Scheduler submit_task: Task {task_id} sent to actor.")
        else:
            # Handle other task types if necessary
            logger.info(f"Task {task_id} is type '{task_type}', not dispatching to agent worker.")
            # Optionally, mark as failed or completed if it's a simple task type
            # await self.metadata_store.update_task_status(task_id, TaskStatus.COMPLETED) # Example

        # Return the task object that was actually persisted/returned by the store
        return persisted_task

    # Removed start/stop methods as they are not needed with Dramatiq


# --- Agent Task Execution Logic ---

async def _run_agent_task_logic(
    task_id: str,
    goal: str,
    input_data: Dict[str, Any],
    metadata_store: BaseMetadataStore, # Accept store instance
    mcp_client: OpsMcpClient # Accept MCP client instance
):
    logger.info(f"VERBOSE_LOG: [_run_agent_task_logic] Actor logic started for task {task_id}.")
    """Helper function containing the core logic for running an agent task."""
    logger.info(f"Starting agent task logic for task_id: {task_id}, goal: {goal}")
    # metadata_store and mcp_client are now passed as arguments

    logger.info(f"Task {task_id}: Entered _run_agent_task_logic.")
    try:
        # Ensure the store is valid before proceeding (basic check)
        if not metadata_store:
             logger.error(f"Task {task_id}: Metadata store not provided. Aborting.")
             # Cannot update status without a store
             return
 
        logger.info(f"VERBOSE_LOG: Task {task_id}: Updating status to RUNNING...")
        await metadata_store.update_task_status(task_id, TaskStatus.RUNNING)
        # Explicitly commit the session *after* status update, *before* agent run
        await metadata_store._session.commit()
        logger.info(f"VERBOSE_LOG: Task {task_id}: Status updated to RUNNING and session committed.")

        # --- Agent Setup ---
        logger.info(f"VERBOSE_LOG: Task {task_id}: Initializing agent components (Memory, Tools, Security)...")
        memory_instance = ShortTermMemory()
        logger.info(f"VERBOSE_LOG: Task {task_id}: ShortTermMemory initialized.")
        tool_registry_instance = ToolRegistry()
        logger.info(f"VERBOSE_LOG: Task {task_id}: ToolRegistry initialized.")
        security_manager_instance = DefaultSecurityManager()
        logger.info(f"VERBOSE_LOG: Task {task_id}: DefaultSecurityManager initialized.")
        logger.info(f"VERBOSE_LOG: Task {task_id}: Base agent components initialized.")

        # Instantiate LLM Client and Planner based on config
        try:
            logger.info(f"VERBOSE_LOG: Task {task_id}: Getting LLM client...")
            llm_client_instance = get_llm_client()
            logger.info(f"VERBOSE_LOG: Task {task_id}: LLM client obtained: {type(llm_client_instance).__name__}")
            logger.info(f"VERBOSE_LOG: Task {task_id}: Getting planner...")
            planner_instance = get_planner(llm_client=llm_client_instance)
            logger.info(f"VERBOSE_LOG: Task {task_id}: Planner obtained: {type(planner_instance).__name__}")
        except Exception as config_err:
             logger.exception(f"Failed to configure LLM/Planner for task {task_id}: {config_err}")
             await metadata_store.update_task_output(
                 task_id=task_id,
                 result={"error": "Agent configuration failed."},
                 error_message=f"LLM/Planner setup error: {config_err}"
             )
             await metadata_store.update_task_status(task_id, TaskStatus.FAILED)
             return # Stop execution if config fails

        # Inject MCP Proxy Tool if MCP client is available
        # Note: Checking _is_running might be less reliable if client startup is complex.
        # Consider a more robust check or assume it's ready if provided.
        logger.info(f"VERBOSE_LOG: Task {task_id}: Checking for MCP client...")
        if mcp_client:
            logger.info(f"VERBOSE_LOG: Task {task_id}: MCP client provided.")
            logger.info(f"Task {task_id}: MCP client found. Attempting to inject proxy tool...")
            try:
                proxy_tool = MCPProxyTool(mcp_client=mcp_client)
                tool_registry_instance.add_tool(proxy_tool)
                logger.info(f"VERBOSE_LOG: Task {task_id}: MCP Proxy Tool injected.")
            except ImportError:
                logger.warning("MCP Proxy Tool spec not found in agentkit. Skipping injection.")
            except Exception as proxy_err:
                logger.exception(f"Failed to register MCP Proxy tool for task {task_id}: {proxy_err}")
                # Decide if this is fatal - maybe just log and continue without proxy?

        # Instantiate Long-Term Memory
        logger.info(f"VERBOSE_LOG: Task {task_id}: Getting Long-Term Memory...")
        long_term_memory_instance = get_long_term_memory()
        logger.info(f"VERBOSE_LOG: Task {task_id}: LTM obtained: {type(long_term_memory_instance).__name__ if long_term_memory_instance else 'None'}")

        logger.info(f"VERBOSE_LOG: Task {task_id}: Initializing Agent instance...")
        agent = Agent(
            memory=memory_instance,
            long_term_memory=long_term_memory_instance, # Pass LTM instance
            planner=planner_instance, # Use configured planner
            tool_manager=tool_registry_instance,
            security_manager=security_manager_instance,
        )
        logger.info(f"VERBOSE_LOG: Task {task_id}: Agent initialized.")
        # --- Agent Execution ---
        # logger.warning(f"DEBUG: Skipping agent.run and memory.get_context for task {task_id}")
        # await asyncio.sleep(0.01)
        logger.info(f"VERBOSE_LOG: Task {task_id}: >>> Starting agent.run(goal='{goal}')...")
        agent_result = await agent.run(goal=goal)
        logger.info(f"VERBOSE_LOG: Task {task_id}: <<< agent.run() finished.")
        # agent_result = {"status": "Success", "output": "DEBUG: Skipped agent execution"}
        logger.info(f"VERBOSE_LOG: Agent task {task_id} completed. Raw Result: {agent_result}")

        # --- Update Metadata Store ---
        # final_status = TaskStatus.COMPLETED
        logger.info(f"VERBOSE_LOG: Task {task_id}: Getting final memory context...")
        memory_content = await agent.memory.get_context()
        logger.info(f"VERBOSE_LOG: Task {task_id}: Final memory context retrieved.")
        # memory_content = ["DEBUG: Skipped memory retrieval"] # Mock memory
        task_result_data = {
            "agent_outcome": agent_result,
            "memory_history": memory_content, # Include memory
        }
        # Determine status and error message based on agent_result
        error_message = None
        # Check if the result indicates a failure (e.g., error string from planning)
        if isinstance(agent_result, str) and ("failed" in agent_result.lower() or "error" in agent_result.lower()):
             final_status = TaskStatus.FAILED
             error_message = agent_result # Use the returned string as the error message
        # Also check for dictionary-based failure status if agent returns that
        elif isinstance(agent_result, dict) and agent_result.get("status") == "Failed":
            final_status = TaskStatus.FAILED
            error_message = agent_result.get("error", "Agent failed without specific error message.")
        else:
            # Otherwise, assume completion
            final_status = TaskStatus.COMPLETED
            error_message = None # Ensure error_message is None on success

        # Update output first
        logger.info(f"VERBOSE_LOG: Task {task_id}: Updating task output in store...")
        await metadata_store.update_task_output(
            task_id=task_id,
            result=task_result_data
        )
        logger.info(f"VERBOSE_LOG: Task {task_id}: Task output updated.")
        # Explicitly update status after output
        logger.info(f"VERBOSE_LOG: Task {task_id}: Updating final status to {final_status}...")
        await metadata_store.update_task_status(task_id, final_status, error_message=error_message)
        logger.info(f"VERBOSE_LOG: Updated metadata for task {task_id} with status {final_status}")
        logger.info(f"VERBOSE_LOG: [_run_agent_task_logic] Agent task {task_id} completed successfully.")

    except TaskNotFoundError:
        logger.error(f"Task {task_id} not found during agent execution.")
        # Cannot update task if not found
    except Exception as e:
        logger.error(f"[_run_agent_task_logic] Agent task {task_id} failed with unexpected error: {e}\n{traceback.format_exc()}", exc_info=False) # Log full traceback
        if metadata_store: # Check if store is available before trying to update
            try:
                # Attempt to mark the task as failed in the store
                # Update output with error info
                await metadata_store.update_task_output(
                    task_id=task_id,
                    result={"error": "Agent execution failed unexpectedly."}
                )
                # Update status and error message separately
                await metadata_store.update_task_status(
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=str(e) # Pass error message here
                )
            except TaskNotFoundError:
                 logger.error(f"Task {task_id} not found when trying to report agent failure.")
            except Exception as store_e:
                logger.exception(f"Failed to update metadata store for failed task {task_id}: {store_e}")
        else:
            logger.error("Metadata store unavailable to report agent failure.")
# --- Dramatiq Actor Definition ---

# Define the core implementation function first
# Define a timeout for agent execution
AGENT_EXECUTION_TIMEOUT = 20.0 # seconds (Increased from 5.0)

async def _execute_agent_task_actor_impl(task_id: str, goal: str, input_data: Dict[str, Any]): # Changed back to async def
    """
    Core logic for the Dramatiq actor that executes agent tasks asynchronously.
    Manages its own database session and metadata store instance.
    """
    # <<< ADDED DEBUG LOG >>>
    logger.critical(f"!!!!!! ACTOR ENTRY POINT REACHED for task: {task_id} !!!!!!")
    # <<< END ADDED DEBUG LOG >>>
    # <<< ADDED DEBUG LOG >>>
    logger.critical(f"!!!!!! VERBOSE_LOG: ACTOR ENTRY POINT REACHED for task: {task_id} !!!!!!")
    # <<< END ADDED DEBUG LOG >>>
    logger.info(f"VERBOSE_LOG: Dramatiq actor received task: {task_id}")
    session: Optional[AsyncSession] = None
    metadata_store: Optional[SqlMetadataStore] = None # Use specific type for instantiation

    try:
        logger.info(f"VERBOSE_LOG: Actor {task_id}: Creating DB session and metadata store...")
        # Create a new session for this actor execution
        session = async_session_factory() # Use the factory to get a session
        metadata_store = SqlMetadataStore(session) # Instantiate with the session
        # metadata_store = None # Placeholder for sync test - REMOVED
        logger.info(f"VERBOSE_LOG: Actor {task_id}: DB session and store created.")
        logger.info(f"VERBOSE_LOG: Actor {task_id}: Getting MCP client...")
        mcp_client = get_mcp_client() # Get the MCP client via dependency function
        # mcp_client = None # Placeholder for sync test - REMOVED
        logger.info(f"VERBOSE_LOG: Actor {task_id}: MCP client obtained.")

        # --- Load testing hook ---
        mock_delay_ms_str = os.getenv("OPS_CORE_LOAD_TEST_MOCK_AGENT_DELAY_MS")
        if mock_delay_ms_str:
            try:
                delay_ms = int(mock_delay_ms_str)
                logger.warning(f"LOAD TEST MODE: Mocking agent execution with {delay_ms}ms delay for task {task_id}.")
                await asyncio.sleep(delay_ms / 1000.0) # Use await for sleep
                # Simulate success for load testing using the actor's store instance
                await metadata_store.update_task_output(task_id=task_id, result={"mock_result": "load_test_success"}) # Use await
                await metadata_store.update_task_status(task_id, TaskStatus.COMPLETED) # Use await
                logger.info(f"LOAD TEST MODE: Mock agent task {task_id} completed.")
                return # Skip real execution
            except ValueError:
                logger.error(f"Invalid OPS_CORE_LOAD_TEST_MOCK_AGENT_DELAY_MS value: {mock_delay_ms_str}. Proceeding with real execution.")
            except Exception as mock_err:
                 logger.exception(f"Error during mock agent execution for task {task_id}: {mock_err}")
                 # Attempt to mark as failed even in mock mode
                 try:
                     await metadata_store.update_task_output(task_id=task_id, result={"error": f"Mock execution error: {mock_err}"}) # Update output on error
                     await metadata_store.update_task_status(task_id, TaskStatus.FAILED, error_message=f"Mock execution error: {mock_err}") # Update status on error
                     # pass # Placeholder for sync test - REMOVED
                 except Exception as store_err_mock:
                     logger.exception(f"Failed to update store after mock execution error for task {task_id}: {store_err_mock}")
                 return # Stop execution

        # --- Call the actual logic with a timeout ---
        logger.info(f"VERBOSE_LOG: Actor {task_id}: Preparing to call _run_agent_task_logic.")
        try:
            logger.info(f"VERBOSE_LOG: Running agent logic for task {task_id} via asyncio.wait_for...")
            await asyncio.wait_for( # Use await for the timeout wrapper
                _run_agent_task_logic(
                    task_id=task_id,
                    goal=goal,
                    input_data=input_data,
                    metadata_store=metadata_store,
                    mcp_client=mcp_client
                ),
                timeout=AGENT_EXECUTION_TIMEOUT
            )
            logger.info(f"VERBOSE_LOG: Actor {task_id}: Agent logic completed successfully via wait_for.")
        except asyncio.TimeoutError:
            logger.error(f"Actor {task_id}: Agent execution timed out after {AGENT_EXECUTION_TIMEOUT} seconds.")
            if metadata_store:
                try:
                    # Update output first
                    await metadata_store.update_task_output( # Use await
                        task_id=task_id,
                        result={"error": f"Agent execution timed out after {AGENT_EXECUTION_TIMEOUT}s."}
                    )
                     # Update status and error message separately
                    await metadata_store.update_task_status( # Use await
                        task_id=task_id,
                        status=TaskStatus.FAILED,
                        error_message=f"Agent execution timed out after {AGENT_EXECUTION_TIMEOUT}s."
                    )
                    # pass # Placeholder for sync test - REMOVED
                except Exception as store_err_timeout:
                     logger.exception(f"Actor {task_id}: Failed to update store after agent timeout: {store_err_timeout}")
            # Do not proceed further if timed out
            return

    except Exception as actor_err:
        # Catch broad exceptions at the actor level to log failure
        logger.exception(f"Actor {task_id}: Caught exception during execution: {actor_err}")
        logger.exception(f"Dramatiq actor failed unexpectedly for task {task_id}: {actor_err}")
        # Attempt to mark task as failed if store was initialized
        if metadata_store:
            try:
                # Update output with error info
                await metadata_store.update_task_output( # Use await
                    task_id=task_id,
                    result={"error": "Actor execution failed unexpectedly."}
                )
                 # Update status and error message separately
                await metadata_store.update_task_status( # Use await
                    task_id=task_id,
                    status=TaskStatus.FAILED,
                    error_message=str(actor_err) # Pass error message here
                )
                # pass # Placeholder for sync test - REMOVED
            except Exception as final_store_err:
                logger.exception(f"Actor {task_id}: Failed to update store after actor-level failure: {final_store_err}")
    finally:
        # Ensure the session is closed
        if session:
            logger.info(f"VERBOSE_LOG: Actor {task_id}: Closing database session in finally block...")
            await session.close() # Use await to close async session

# Apply the decorator directly to the implementation function.
# Dramatiq handles re-registration gracefully if the module is imported multiple times.
execute_agent_task_actor = dramatiq.actor(_execute_agent_task_actor_impl, actor_name="execute_agent_task_actor")
