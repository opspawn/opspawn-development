# agentkit/tests/core/test_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock, call

from agentkit.core.agent import Agent
from agentkit.core.interfaces import (
    BaseLongTermMemory, # Import LTM interface
    BaseMemory,
    BasePlanner,
    BaseSecurityManager,
    BaseToolManager,
)
# Import Plan and PlanStep from their specific module
from agentkit.core.interfaces.planner import Plan, PlanStep
from agentkit.memory.short_term import ShortTermMemory # For type checking test
from agentkit.tools.schemas import ToolResult # Import ToolResult


# --- Fixtures for Mocks ---

@pytest.fixture
def mock_memory():
    """Fixture for a mocked BaseMemory."""
    mock = MagicMock(spec=BaseMemory)
    # Mock the actual async methods defined in the interface
    mock.get_context = AsyncMock(return_value=[]) # Default empty context
    mock.add_message = AsyncMock()
    mock.clear = AsyncMock()
    return mock

@pytest.fixture
def mock_planner():
    """Fixture for a mocked BasePlanner."""
    mock = MagicMock(spec=BasePlanner)
    # Default plan: a single final_answer step (as a Plan object)
    default_plan_obj = Plan(steps=[PlanStep(action_type="final_answer", details={"answer": "Mock answer"})])
    mock.plan = AsyncMock(return_value=default_plan_obj) # Return Plan object
    return mock

@pytest.fixture
def mock_tool_manager():
    """Fixture for a mocked BaseToolManager."""
    mock = MagicMock(spec=BaseToolManager)
    # Mock execute_tool if needed for specific tests later
    mock.execute_tool = AsyncMock()
    return mock

@pytest.fixture
def mock_security_manager():
    """Fixture for a mocked BaseSecurityManager."""
    mock = MagicMock(spec=BaseSecurityManager)
    # Mock the actual async method defined in the interface
    mock.check_permissions = AsyncMock(return_value=True) # Default: allow execution
    return mock

@pytest.fixture
def mock_long_term_memory():
    """Fixture for a mocked BaseLongTermMemory."""
    mock = MagicMock(spec=BaseLongTermMemory)
    mock.add_memory = AsyncMock()
    mock.search_memory = AsyncMock(return_value=[]) # Default empty results
    return mock

# --- Test Cases ---

def test_agent_initialization_success(
    mock_memory, mock_long_term_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests successful agent initialization with valid mocks, including LTM."""
    agent = Agent(
        memory=mock_memory,
        long_term_memory=mock_long_term_memory, # Add LTM
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )
    assert agent.memory is mock_memory
    assert agent.long_term_memory is mock_long_term_memory # Check LTM
    assert agent.planner is mock_planner
    assert agent.tool_manager is mock_tool_manager
    assert agent.security_manager is mock_security_manager

def test_agent_initialization_defaults(mock_long_term_memory):
    """Tests agent initialization with default components."""
    # Test with only LTM provided, others should default
    agent = Agent(long_term_memory=mock_long_term_memory)
    assert isinstance(agent.memory, ShortTermMemory)
    assert agent.long_term_memory is mock_long_term_memory
    # Check other defaults if needed

def test_agent_initialization_type_error(
    mock_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests that TypeError is raised for invalid dependency types."""
    with pytest.raises(TypeError, match="memory must be an instance of BaseMemory"):
        Agent(memory="not_memory", planner=mock_planner, tool_manager=mock_tool_manager, security_manager=mock_security_manager)

    # Test other dependencies similarly
    with pytest.raises(TypeError, match="planner must be an instance of BasePlanner"):
        Agent(memory=mock_memory, planner="not_planner", tool_manager=mock_tool_manager, security_manager=mock_security_manager)

    with pytest.raises(TypeError, match="tool_manager must be an instance of BaseToolManager"):
        Agent(memory=mock_memory, planner=mock_planner, tool_manager="not_tm", security_manager=mock_security_manager)

    with pytest.raises(TypeError, match="security_manager must be an instance of BaseSecurityManager"):
        Agent(memory=mock_memory, planner=mock_planner, tool_manager=mock_tool_manager, security_manager="not_sm")

    # Test LTM type error
    with pytest.raises(TypeError, match="long_term_memory must be an instance of BaseLongTermMemory or None"):
        Agent(memory=mock_memory, long_term_memory="not_ltm", planner=mock_planner, tool_manager=mock_tool_manager, security_manager=mock_security_manager)


# --- Run Tests ---

@pytest.mark.asyncio
async def test_agent_run_simple_final_answer_no_ltm(
    mock_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests a simple run with no LTM configured."""
    goal = "Simple task"
    final_answer = "Mock answer"
    plan = Plan(steps=[PlanStep(action_type="final_answer", details={"answer": final_answer})])
    mock_planner.plan.return_value = plan

    agent = Agent(
        memory=mock_memory,
        long_term_memory=None, # Explicitly no LTM
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )

    result = await agent.run_async(goal)

    # Check planner call - Context should not include LTM results
    expected_context = {'messages': [], 'profile': {}, 'available_tools': [], 'retrieved_memories': ''}
    mock_planner.plan.assert_awaited_once_with(goal=goal, context=expected_context)

    # Check security call
    mock_security_manager.check_permissions.assert_awaited_once_with(
        action="final_answer", context={"step": plan.steps[0]}
    )

    # Check short-term memory calls
    expected_stm_calls = [
        call(role="user", content=goal),
        call(role="assistant", content="Step 1 outcome: Mock answer"),
    ]
    mock_memory.add_message.assert_has_calls(expected_stm_calls, any_order=False)

    # Check final result
    assert result == final_answer


@pytest.mark.asyncio
async def test_agent_run_security_denial_no_ltm(
    mock_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests security denial with no LTM configured."""
    goal = "Risky task"
    plan_obj = Plan(steps=[PlanStep(action_type="tool_call", details={"tool_name": "risky_tool", "arguments": {}})])
    mock_planner.plan.return_value = plan_obj
    mock_security_manager.check_permissions.return_value = False

    agent = Agent(
        memory=mock_memory,
        long_term_memory=None, # Explicitly no LTM
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )

    result = await agent.run_async(goal)

    # Check security call
    mock_security_manager.check_permissions.assert_awaited_once_with(
        action="tool_call:risky_tool", context={"step": plan_obj.steps[0]}
    )

    # Check short-term memory calls
    expected_stm_calls = [
        call(role="user", content=goal),
        call(role="assistant", content="Step 1 outcome: Permission denied for action 'tool_call:risky_tool'."),
    ]
    mock_memory.add_message.assert_has_calls(expected_stm_calls, any_order=False)

    # Check final result
    assert result == "Task failed at step 1: Permission denied for action 'tool_call:risky_tool'."
    mock_tool_manager.execute_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_run_no_steps_in_plan_no_ltm(
    mock_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests empty plan scenario with no LTM configured."""
    goal = "Task with no steps"
    plan_obj = Plan(steps=[])
    mock_planner.plan.return_value = plan_obj

    agent = Agent(
        memory=mock_memory,
        long_term_memory=None, # Explicitly no LTM
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )

    result = await agent.run_async(goal)

    # Check planner call
    expected_context = {'messages': [], 'profile': {}, 'available_tools': [], 'retrieved_memories': ''}
    mock_planner.plan.assert_awaited_once_with(goal=goal, context=expected_context)

    # Check short-term memory calls
    expected_stm_calls = [
        call(role="user", content=goal),
        call(role="assistant", content="Planner returned an empty plan. Task cannot proceed."),
    ]
    mock_memory.add_message.assert_has_calls(expected_stm_calls, any_order=False)

    # Check final result
    assert result == "Planner returned an empty plan. Task cannot proceed."
    mock_security_manager.check_permissions.assert_not_called()
    mock_tool_manager.execute_tool.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_clear_memory(
    mock_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests clearing the agent's short-term memory."""
    agent = Agent(
        memory=mock_memory,
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )
    await agent.memory.clear() # Clear short-term memory
    mock_memory.clear.assert_awaited_once()
    # Note: Agent doesn't directly manage LTM clearing


@pytest.mark.asyncio
async def test_agent_run_tool_call_no_ltm(
    mock_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests a tool call scenario with no LTM configured."""
    goal = "Use calculator"
    tool_name = "calculator"
    tool_input = {"query": "2+2"}
    tool_output = {"result": 4}
    plan_obj = Plan(steps=[PlanStep(action_type="tool_call", details={"tool_name": tool_name, "arguments": tool_input})])
    tool_result = ToolResult(tool_name=tool_name, tool_args=tool_input, output=tool_output, error=None)

    mock_planner.plan.return_value = plan_obj
    mock_tool_manager.execute_tool.return_value = tool_result

    agent = Agent(
        memory=mock_memory,
        long_term_memory=None, # Explicitly no LTM
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )

    result = await agent.run_async(goal)

    # Check planner call
    expected_context = {'messages': [], 'profile': {}, 'available_tools': [], 'retrieved_memories': ''}
    mock_planner.plan.assert_awaited_once_with(goal=goal, context=expected_context)

    # Check security call
    mock_security_manager.check_permissions.assert_awaited_once_with(
        action="tool_call:calculator", context={"step": plan_obj.steps[0]}
    )

    # Check tool manager call
    mock_tool_manager.execute_tool.assert_awaited_once_with(tool_name, tool_input)

    # Check short-term memory calls
    expected_stm_calls = [
        call(role="user", content=goal),
        call(role="tool", content=f"Tool '{tool_name}' called with args {tool_input}. Result: {tool_output}", metadata={'tool_result': tool_result.model_dump()}),
        call(role="assistant", content="Final Result: Plan executed but no explicit completion step found.")
    ]
    mock_memory.add_message.assert_has_calls(expected_stm_calls, any_order=False)

    # Check final result
    assert result == "Plan executed but no explicit completion step found."


@pytest.mark.asyncio
async def test_agent_run_tool_call_failure_no_ltm(
    mock_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests a failed tool call scenario with no LTM configured."""
    goal = "Use broken tool"
    tool_name = "broken_calculator"
    tool_input = {"query": "1/0"}
    tool_error = "Division by zero"
    plan_obj = Plan(steps=[PlanStep(action_type="tool_call", details={"tool_name": tool_name, "arguments": tool_input})])
    tool_result = ToolResult(tool_name=tool_name, tool_args=tool_input, output=None, error=tool_error)

    mock_planner.plan.return_value = plan_obj
    mock_tool_manager.execute_tool.return_value = tool_result

    agent = Agent(
        memory=mock_memory,
        long_term_memory=None, # Explicitly no LTM
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )

    result = await agent.run_async(goal)

    # Check planner, security, tool manager calls
    expected_context = {'messages': [], 'profile': {}, 'available_tools': [], 'retrieved_memories': ''}
    mock_planner.plan.assert_awaited_once_with(goal=goal, context=expected_context)
    mock_security_manager.check_permissions.assert_awaited_once_with(
        action="tool_call:broken_calculator", context={"step": plan_obj.steps[0]}
    )
    mock_tool_manager.execute_tool.assert_awaited_once_with(tool_name, tool_input)

    # Check short-term memory calls
    expected_stm_calls = [
        call(role="user", content=goal),
        call(role="tool", content=f"Tool '{tool_name}' called with args {tool_input}. Failed: {tool_error}", metadata={'tool_result': tool_result.model_dump()}),
    ]
    mock_memory.add_message.assert_has_calls(expected_stm_calls, any_order=False)

    # Check final result
    assert result == f"Task failed at step 1: {tool_error}"


@pytest.mark.asyncio
async def test_agent_run_mcp_proxy_call_success_no_ltm(
    mock_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests a successful MCP proxy call with no LTM configured."""
    goal = "Get weather via MCP"
    mcp_tool_name = "mcp_proxy_tool"
    mcp_tool_input = {"server_name": "weather", "tool_name": "get", "arguments": {"city": "L"}}
    mcp_tool_output = {"temp": 15}
    plan_obj = Plan(steps=[PlanStep(action_type="tool_call", details={"tool_name": mcp_tool_name, "arguments": mcp_tool_input})])
    tool_result = ToolResult(tool_name=mcp_tool_name, tool_args=mcp_tool_input, output=mcp_tool_output, error=None)

    mock_planner.plan.return_value = plan_obj
    mock_tool_manager.execute_tool.return_value = tool_result

    agent = Agent(
        memory=mock_memory,
        long_term_memory=None, # Explicitly no LTM
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )

    result = await agent.run_async(goal)

    # Check planner call
    expected_context = {'messages': [], 'profile': {}, 'available_tools': [], 'retrieved_memories': ''}
    mock_planner.plan.assert_awaited_once_with(goal=goal, context=expected_context)

    # Check security call
    mock_security_manager.check_permissions.assert_awaited_once_with(
        action=f"tool_call:{mcp_tool_name}", context={"step": plan_obj.steps[0]}
    )

    # Check tool manager call
    mock_tool_manager.execute_tool.assert_awaited_once_with(mcp_tool_name, mcp_tool_input)

    # Check short-term memory calls
    expected_stm_calls = [
        call(role="user", content=goal),
        call(role="tool", content=f"Tool '{mcp_tool_name}' called with args {mcp_tool_input}. Result: {mcp_tool_output}", metadata={'tool_result': tool_result.model_dump()}),
        call(role="assistant", content="Final Result: Plan executed but no explicit completion step found.")
    ]
    mock_memory.add_message.assert_has_calls(expected_stm_calls, any_order=False)

    # Check final result
    assert result == "Plan executed but no explicit completion step found."


@pytest.mark.asyncio
async def test_agent_run_mcp_proxy_call_failure_no_ltm(
    mock_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests a failed MCP proxy call with no LTM configured."""
    goal = "Get weather via MCP (fail)"
    mcp_tool_name = "mcp_proxy_tool"
    mcp_tool_input = {"server_name": "weather", "tool_name": "get", "arguments": {"city": "Inv"}}
    mcp_tool_error = "MCP server error: City not found"
    plan_obj = Plan(steps=[PlanStep(action_type="tool_call", details={"tool_name": mcp_tool_name, "arguments": mcp_tool_input})])
    tool_result = ToolResult(tool_name=mcp_tool_name, tool_args=mcp_tool_input, output=None, error=mcp_tool_error)

    mock_planner.plan.return_value = plan_obj
    mock_tool_manager.execute_tool.return_value = tool_result

    agent = Agent(
        memory=mock_memory,
        long_term_memory=None, # Explicitly no LTM
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )

    result = await agent.run_async(goal)

    # Check planner, security, tool manager calls
    expected_context = {'messages': [], 'profile': {}, 'available_tools': [], 'retrieved_memories': ''}
    mock_planner.plan.assert_awaited_once_with(goal=goal, context=expected_context)
    mock_security_manager.check_permissions.assert_awaited_once_with(
        action=f"tool_call:{mcp_tool_name}", context={"step": plan_obj.steps[0]}
    )
    mock_tool_manager.execute_tool.assert_awaited_once_with(mcp_tool_name, mcp_tool_input)

    # Check short-term memory calls
    expected_stm_calls = [
        call(role="user", content=goal),
        call(role="tool", content=f"Tool '{mcp_tool_name}' called with args {mcp_tool_input}. Failed: {mcp_tool_error}", metadata={'tool_result': tool_result.model_dump()}),
    ]
    mock_memory.add_message.assert_has_calls(expected_stm_calls, any_order=False)

    # Check final result
    assert result == f"Task failed at step 1: {mcp_tool_error}"

# --- LTM Specific Tests ---

@pytest.mark.asyncio
async def test_agent_run_with_ltm_search_and_add(
    mock_memory, mock_long_term_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests LTM search at start and add at end on success."""
    goal = "Analyze past data"
    final_answer = "Analysis complete based on past data."
    retrieved_memory_text = "Past data point 1"
    retrieved_memory_score = 0.9

    # Mock LTM search result
    mock_long_term_memory.search_memory.return_value = [(retrieved_memory_text, retrieved_memory_score)]

    # Mock planner to return a final answer
    plan = Plan(steps=[PlanStep(action_type="final_answer", details={"answer": final_answer})])
    mock_planner.plan.return_value = plan

    agent = Agent(
        memory=mock_memory,
        long_term_memory=mock_long_term_memory,
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )

    result = await agent.run_async(goal)

    # Check LTM search call
    mock_long_term_memory.search_memory.assert_awaited_once_with(query=goal, n_results=3)

    # Check planner call - context should include retrieved memories
    expected_ltm_context = f"Relevant information from past tasks:\n- {retrieved_memory_text} (Score: {retrieved_memory_score:.4f})"
    expected_context = {'messages': [], 'profile': {}, 'available_tools': [], 'retrieved_memories': expected_ltm_context}
    mock_planner.plan.assert_awaited_once_with(goal=goal, context=expected_context)

    # Check security call
    mock_security_manager.check_permissions.assert_awaited_once_with(
        action="final_answer", context={"step": plan.steps[0]}
    )

    # Check short-term memory calls
    expected_stm_calls = [
        call(role="user", content=goal),
        call(role="assistant", content="Step 1 outcome: Analysis complete based on past data."),
    ]
    mock_memory.add_message.assert_has_calls(expected_stm_calls, any_order=False)

    # Check LTM add call at the end
    expected_ltm_add_text = f"Goal: {goal}\nFinal Result: {final_answer}"
    expected_ltm_add_metadata = {"goal": goal, "status": "completed"}
    mock_long_term_memory.add_memory.assert_awaited_once_with(
        text=expected_ltm_add_text, metadata=expected_ltm_add_metadata
    )

    # Check final result
    assert result == final_answer


@pytest.mark.asyncio
async def test_agent_run_with_ltm_add_on_failure(
    mock_memory, mock_long_term_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests LTM add is called at the end even on task failure."""
    goal = "Task that fails"
    tool_name = "failing_tool"
    tool_error = "It broke"
    plan_obj = Plan(steps=[PlanStep(action_type="tool_call", details={"tool_name": tool_name, "arguments": {}})])
    tool_result = ToolResult(tool_name=tool_name, tool_args={}, output=None, error=tool_error)

    mock_planner.plan.return_value = plan_obj
    mock_tool_manager.execute_tool.return_value = tool_result
    mock_long_term_memory.search_memory.return_value = [] # No initial memories

    agent = Agent(
        memory=mock_memory,
        long_term_memory=mock_long_term_memory,
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )

    result = await agent.run_async(goal)

    # Check LTM search call
    mock_long_term_memory.search_memory.assert_awaited_once_with(query=goal, n_results=3)

    # Check LTM add call at the end
    final_result_text = f"Task failed at step 1: {tool_error}"
    expected_ltm_add_text = f"Goal: {goal}\nFinal Result: {final_result_text}"
    expected_ltm_add_metadata = {"goal": goal, "status": "failed"}
    mock_long_term_memory.add_memory.assert_awaited_once_with(
        text=expected_ltm_add_text, metadata=expected_ltm_add_metadata
    )

    # Check final result
    assert result == final_result_text


@pytest.mark.asyncio
async def test_agent_run_ltm_search_fails_gracefully(
    mock_memory, mock_long_term_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests that agent continues if LTM search fails."""
    goal = "Search fails"
    final_answer = "Completed despite LTM search failure."
    plan = Plan(steps=[PlanStep(action_type="final_answer", details={"answer": final_answer})])

    # Mock LTM search to raise an error
    mock_long_term_memory.search_memory.side_effect = RuntimeError("LTM DB unavailable")
    mock_planner.plan.return_value = plan

    agent = Agent(
        memory=mock_memory,
        long_term_memory=mock_long_term_memory,
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )

    result = await agent.run_async(goal)

    # Check LTM search was called
    mock_long_term_memory.search_memory.assert_awaited_once_with(query=goal, n_results=3)

    # Check planner was still called (with empty retrieved memories)
    expected_context = {'messages': [], 'profile': {}, 'available_tools': [], 'retrieved_memories': ''}
    mock_planner.plan.assert_awaited_once_with(goal=goal, context=expected_context)

    # Check LTM add was still called at the end
    expected_ltm_add_text = f"Goal: {goal}\nFinal Result: {final_answer}"
    mock_long_term_memory.add_memory.assert_awaited_once_with(
        text=expected_ltm_add_text, metadata={"goal": goal, "status": "completed"}
    )

    # Check final result
    assert result == final_answer


@pytest.mark.asyncio
async def test_agent_run_ltm_add_fails_gracefully(
    mock_memory, mock_long_term_memory, mock_planner, mock_tool_manager, mock_security_manager
):
    """Tests that agent completes if LTM add fails at the end."""
    goal = "Add fails"
    final_answer = "Completed, but LTM add failed."
    plan = Plan(steps=[PlanStep(action_type="final_answer", details={"answer": final_answer})])

    # Mock LTM add to raise an error
    mock_long_term_memory.add_memory.side_effect = RuntimeError("LTM DB write error")
    mock_long_term_memory.search_memory.return_value = [] # No initial memories
    mock_planner.plan.return_value = plan

    agent = Agent(
        memory=mock_memory,
        long_term_memory=mock_long_term_memory,
        planner=mock_planner,
        tool_manager=mock_tool_manager,
        security_manager=mock_security_manager,
    )

    result = await agent.run_async(goal)

    # Check LTM search was called
    mock_long_term_memory.search_memory.assert_awaited_once_with(query=goal, n_results=3)

    # Check LTM add was called
    expected_ltm_add_text = f"Goal: {goal}\nFinal Result: {final_answer}"
    mock_long_term_memory.add_memory.assert_awaited_once_with(
        text=expected_ltm_add_text, metadata={"goal": goal, "status": "completed"}
    )

    # Check final result (should still be the agent's result)
    assert result == final_answer
