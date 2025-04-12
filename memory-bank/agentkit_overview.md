# Agentkit Overview

`agentkit` is a modular Python toolkit designed for building LLM-powered agents. It provides core components and interfaces for planning, memory management, tool execution, and security, allowing developers to construct sophisticated agents with customizable capabilities.

## Core Components & Interfaces

-   **`Agent` (`core/agent.py`):** The central orchestrator that coordinates the agent's lifecycle, managing interactions between the planner, memory, and tool manager.
-   **Interfaces (`core/interfaces/`):** Abstract base classes define the contracts for key components:
    -   `BasePlanner`: Defines the interface for task planning modules (e.g., generating sequences of actions).
    -   `BaseMemory`: Defines the interface for short-term conversational memory (e.g., storing message history).
    -   `BaseLongTermMemory`: Defines the interface for persistent, searchable long-term memory (e.g., storing facts or past task summaries across sessions).
    -   `BaseToolManager`: Defines the interface for managing and executing tools available to the agent.
    -   `BaseSecurityManager`: Defines the interface for checking permissions before executing actions.
    -   `BaseLlmClient`: Defines the interface for interacting with various Large Language Models.
-   **Planner Implementations (`planning/`):** Concrete planner strategies.
    -   `SimplePlanner`: A basic planner (potentially placeholder).
    -   `ReActPlanner`: Implements the ReAct (Reason + Act) prompting strategy.
    -   `PlaceholderPlanner`: A minimal planner implementation.
-   **Memory Implementations (`memory/`):**
    -   `ShortTermMemory` (`memory/short_term.py`): An in-memory implementation of `BaseMemory` for conversational history.
    -   **`ChromaLongTermMemory` (`memory/long_term/chroma_memory.py`):** An implementation of `BaseLongTermMemory` using ChromaDB for persistent storage and semantic search of text memories. *(Added in Task 6.4)*
-   **Tool Management (`tools/`):** Components for defining, registering, and executing tools.
    -   `ToolRegistry`: Manages a collection of available tools defined by `ToolSpec`.
    -   `Execution`: Handles the safe execution of tool functions.
    -   `Schemas`: Pydantic models for `ToolSpec` and `ToolResult`.
    -   `MCPProxyTool`: A specific tool implementation allowing agents to interact with external MCP servers via `ops-core`.
-   **LLM Clients (`llm_clients/`):** Implementations of `BaseLlmClient` for specific LLM providers (OpenAI, Anthropic, Google Gemini, OpenRouter).

## Agent Run Workflow (Simplified)

1.  **Initialization:** An `Agent` instance is created, injecting implementations for planner, memory (short-term and optionally long-term), tool manager, and security manager.
2.  **Goal Received:** The `run_async` method is called with a user-defined goal.
3.  **LTM Search (Optional):** If a `BaseLongTermMemory` instance is configured, the agent searches it using the goal as a query to retrieve relevant past information.
4.  **Context Preparation:** The agent gathers context, including short-term memory messages, available tool specifications, agent profile, and any retrieved long-term memories.
5.  **Planning:** The `BasePlanner` implementation is called with the goal and context to generate a `Plan` object containing a sequence of `PlanStep`s.
6.  **Execution Loop:** The agent iterates through the plan steps:
    *   **Security Check:** The `BaseSecurityManager` verifies if the action is permitted.
    *   **Action Execution:** Based on the `action_type` (e.g., `tool_call`, `final_answer`), the agent interacts with the `BaseToolManager` or handles the step internally.
    *   **Memory Update:** The outcome of the step (e.g., tool input/output/error, final answer) is added to the short-term `BaseMemory`.
    *   **Loop Control:** The loop continues until a step fails, a `final_answer` step is reached, or all steps are executed.
7.  **LTM Add (Optional):** If a `BaseLongTermMemory` instance is configured, the agent adds a summary of the task (goal and final result) to the long-term store.
8.  **Result:** The final result of the execution (e.g., the final answer, an error message) is returned.
