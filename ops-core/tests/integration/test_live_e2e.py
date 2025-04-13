import pytest
import asyncio
import httpx # Implicitly used by live_api_client
from uuid import UUID, uuid4
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from ops_core.models.tasks import Task, TaskStatus

# Mark all tests in this module as live
# This assumes the fixtures live_api_server, live_dramatiq_worker are running
pytestmark = pytest.mark.live


async def get_task_from_db(session: AsyncSession, task_id_str: str) -> Task | None: # Expect string ID
    """Helper function to retrieve a task from the database."""
    # Query using the correct string field Task.task_id
    result = await session.execute(select(Task).where(Task.task_id == task_id_str))
    return result.scalars().first()


@pytest.mark.asyncio
async def test_submit_task_and_poll_completion(
    live_api_client: httpx.AsyncClient, live_db_session: AsyncSession
):
    """
    Tests submitting a simple task via API, polling for status,
    and verifying completion in the database using live services.

    Requires OPENAI_API_KEY to be set in the environment where pytest is run,
    as the default agent configuration uses OpenAI.
    """
    task_input = {
        "prompt": "Write a short poem about testing code.",
        "task_type": "agent_task" # Added missing required field
    }
    task_id_str: str | None = None
    # task_id: UUID | None = None # Removed unused UUID variable

    # 1. Submit task via API
    response = await live_api_client.post("/api/v1/tasks/", json=task_input)
    assert response.status_code == 201, f"API Error: {response.text}"
    response_data = response.json()
    task_id_str = response_data.get("task_id") # Fetch 'task_id' from response
    assert task_id_str is not None
    # task_id = UUID(task_id_str) # Removed UUID conversion, use task_id_str directly
    print(f"Task submitted with ID: {task_id_str}") # Use task_id_str
    await asyncio.sleep(1) # Add a small delay before polling
 
    # 2. Poll for completion
    max_polls = 30  # Increased polling time for potentially slow LLM calls
    poll_interval = 5 # seconds
    final_status = None
    final_output = None

    for i in range(max_polls):
        print(f"Polling task {task_id_str} (Attempt {i+1}/{max_polls})...") # Use task_id_str
        await asyncio.sleep(poll_interval)
        try:
            response = await live_api_client.get(f"/api/v1/tasks/{task_id_str}") # Use task_id_str (already correct)
            response.raise_for_status() # Raise exception for 4xx/5xx errors
            response_data = response.json()
            status = response_data.get("status")
            final_output = response_data.get("output") # Store latest output

            print(f"  Status: {status}")

            if status == TaskStatus.COMPLETED:
                final_status = TaskStatus.COMPLETED
                break
            elif status == TaskStatus.FAILED:
                final_status = TaskStatus.FAILED
                pytest.fail(f"Task {task_id_str} failed: {final_output}") # Use task_id_str
            # Continue polling if PENDING or RUNNING
        except httpx.HTTPStatusError as e:
            pytest.fail(f"API error during polling: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            pytest.fail(f"Unexpected error during polling: {e}")

    if final_status != TaskStatus.COMPLETED:
        pytest.fail(f"Task {task_id_str} did not complete within timeout ({max_polls * poll_interval}s). Final status: {final_status}") # Use task_id_str

    # 3. Verify final state in DB
    print(f"Verifying final state for task {task_id_str} in DB...") # Use task_id_str
    # Use the live_db_session fixture
    final_task = await get_task_from_db(live_db_session, task_id_str) # Pass task_id_str

    assert final_task is not None, f"Task {task_id_str} not found in database." # Use task_id_str
    assert final_task.status == TaskStatus.COMPLETED
    assert final_task.output is not None
    assert isinstance(final_task.output, str)
    # Basic check on output content - LLM output can vary
    assert len(final_task.output) > 10, "Output seems too short."
    assert "test" in final_task.output.lower() or "code" in final_task.output.lower(), \
           f"Expected keyword not found in output: {final_task.output}"
    print(f"Task {task_id_str} completed successfully and verified in DB.") # Use task_id_str
    print(f"Output:\n{final_task.output}")


@pytest.mark.asyncio
async def test_submit_task_and_expect_failure(
    live_api_client: httpx.AsyncClient, live_db_session: AsyncSession
):
    """
    Tests submitting a task that is expected to fail (e.g., due to LLM config error)
    and verifies the FAILED status.
    """
    # Use a configuration likely to fail if keys aren't set for all providers
    # Or, ideally, the API would allow specifying a non-existent model/provider
    # For now, we rely on the default config potentially failing if keys are missing
    # or if the LLM itself returns an error for a deliberately bad prompt.
    # Let's try forcing a provider that might not have keys set.
    task_input = {
        "prompt": "This prompt is designed to potentially cause an error.",
        "task_type": "agent_task", # Added missing required field
        "agent_config": { # Assuming API supports overriding agent config
            "llm_provider": "non_existent_provider",
            "llm_model": "error-model"
        }
    }
    # If API doesn't support config override, we rely on default failing
    # task_input = {"prompt": "Provide instructions for building a perpetual motion machine."}


    task_id_str: str | None = None
    # task_id: UUID | None = None # Removed unused UUID variable

    # 1. Submit task via API
    # Note: The API might not support overriding agent_config yet.
    # If it doesn't, this test might pass trivially if the default config works.
    # A better approach would be to enhance the API or have specific error-inducing prompts.
    # For now, let's assume the API accepts the config override.
    response = await live_api_client.post("/api/v1/tasks/", json=task_input)

    # If the config override isn't supported, the API might reject it (422)
    # or ignore it and proceed (potentially succeeding).
    # If it *is* supported, the task should be created (201).
    if response.status_code == 422:
        pytest.skip("API does not support agent_config override yet. Skipping failure test.")
        return

    assert response.status_code == 201, f"API Error: {response.text}"
    response_data = response.json()
    task_id_str = response_data.get("task_id") # Fetch 'task_id' from response
    assert task_id_str is not None
    # task_id = UUID(task_id_str) # Removed UUID conversion, use task_id_str directly
    print(f"Task submitted for expected failure with ID: {task_id_str}") # Use task_id_str
    await asyncio.sleep(1) # Add a small delay before polling
 
    # 2. Poll for FAILED status
    max_polls = 20 # Failure might happen faster
    poll_interval = 3 # seconds
    final_status = None
    final_output = None

    for i in range(max_polls):
        print(f"Polling failing task {task_id_str} (Attempt {i+1}/{max_polls})...") # Use task_id_str
        await asyncio.sleep(poll_interval)
        try:
            response = await live_api_client.get(f"/api/v1/tasks/{task_id_str}") # Use task_id_str (already correct)
            response.raise_for_status()
            response_data = response.json()
            status = response_data.get("status")
            final_output = response_data.get("output")

            print(f"  Status: {status}")

            if status == TaskStatus.FAILED:
                final_status = TaskStatus.FAILED
                break
            elif status == TaskStatus.COMPLETED:
                 pytest.fail(f"Task {task_id_str} unexpectedly completed successfully.") # Use task_id_str
            # Continue polling if PENDING or RUNNING
        except httpx.HTTPStatusError as e:
            pytest.fail(f"API error during polling: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            pytest.fail(f"Unexpected error during polling: {e}")

    if final_status != TaskStatus.FAILED:
        pytest.fail(f"Task {task_id_str} did not fail within timeout ({max_polls * poll_interval}s). Final status: {final_status}") # Use task_id_str

    # 3. Verify final state in DB
    print(f"Verifying FAILED state for task {task_id_str} in DB...") # Use task_id_str
    final_task = await get_task_from_db(live_db_session, task_id_str) # Pass task_id_str

    assert final_task is not None, f"Task {task_id_str} not found in database." # Use task_id_str
    assert final_task.status == TaskStatus.FAILED
    assert final_task.output is not None # Should contain error message
    assert isinstance(final_task.output, str)
    assert len(final_task.output) > 5 # Error messages usually have some length
    print(f"Task {task_id_str} failed as expected and verified in DB.") # Use task_id_str
    print(f"Failure Output:\n{final_task.output}")


@pytest.mark.asyncio
async def test_concurrent_task_submissions(
    live_api_client: httpx.AsyncClient, live_db_session: AsyncSession
):
    """
    Tests submitting multiple tasks concurrently and verifying their completion.
    """
    num_tasks = 3
    task_inputs = [{
        "prompt": f"Write a haiku about concurrency number {i+1}.",
        "task_type": "agent_task" # Added missing required field
    } for i in range(num_tasks)]
    # task_ids = [] # Removed unused list
    task_id_strs = []

    # 1. Submit tasks concurrently
    async def submit_task(task_input):
        response = await live_api_client.post("/api/v1/tasks/", json=task_input)
        assert response.status_code == 201, f"API Error: {response.text}"
        response_data = response.json()
        task_id_str = response_data.get("task_id") # Expect 'task_id' (string) now
        assert task_id_str is not None
        # Return only the string task_id
        return task_id_str

    submission_tasks = [submit_task(inp) for inp in task_inputs]
    results = await asyncio.gather(*submission_tasks)
    for task_id_str_result in results: # Unpack only the string ID
        # task_ids.append(task_id_str_result) # Removed unused list append
        task_id_strs.append(task_id_str_result)
        print(f"Concurrent task submitted with ID: {task_id_str_result}") # Use correct variable

    assert len(task_id_strs) == num_tasks # Assert using the correct list

    # 2. Poll for completion of all tasks
    max_polls = 40 # Allow more time for multiple tasks
    poll_interval = 5
    completed_tasks = set()
    failed_tasks = set()

    for i in range(max_polls):
        print(f"Polling concurrent tasks (Attempt {i+1}/{max_polls})...")
        all_done = True
        for task_id_str in task_id_strs: # Iterate only over task_id_strs (already correct)
            if task_id_str in completed_tasks or task_id_str in failed_tasks: # Check using task_id_str
                continue # Already reached terminal state

            all_done = False # At least one task still pending/running
            try:
                response = await live_api_client.get(f"/api/v1/tasks/{task_id_str}") # Use task_id_str (already correct)
                response.raise_for_status()
                response_data = response.json()
                status = response_data.get("status")
                output = response_data.get("output")

                print(f"  Task {task_id_str} Status: {status}") # Use task_id_str

                if status == TaskStatus.COMPLETED:
                    completed_tasks.add(task_id_str) # Add task_id_str
                elif status == TaskStatus.FAILED:
                    failed_tasks.add(task_id_str) # Add task_id_str
                    print(f"  Task {task_id_str} FAILED: {output}") # Use task_id_str

            except httpx.HTTPStatusError as e:
                 # Treat API error during polling as a task failure for verification purposes
                print(f"  API error polling task {task_id_str}: {e.response.status_code} - {e.response.text}") # Use task_id_str
                failed_tasks.add(task_id_str) # Add task_id_str
            except Exception as e:
                print(f"  Unexpected error polling task {task_id_str}: {e}") # Use task_id_str
                failed_tasks.add(task_id_str) # Add task_id_str

        if all_done:
            print("All concurrent tasks reached a terminal state.")
            break

        await asyncio.sleep(poll_interval)
    else:
         pytest.fail(f"Not all concurrent tasks completed within timeout. Completed: {len(completed_tasks)}, Failed: {len(failed_tasks)}")

    # 3. Verify final state in DB for all tasks
    print("Verifying final states for concurrent tasks in DB...")
    final_tasks = {}
    # Fetch results from DB using the collected string IDs
    verification_tasks = [get_task_from_db(live_db_session, task_id_str) for task_id_str in task_id_strs]
    # Fetch DB results sequentially to avoid concurrent session use
    db_results = []
    for task_id_str_to_verify in task_id_strs:
        db_results.append(await get_task_from_db(live_db_session, task_id_str_to_verify))

    for task_id_str, final_task in zip(task_id_strs, db_results): # Iterate using task_id_strs
        assert final_task is not None, f"Task {task_id_str} not found in database." # Use task_id_str
        final_tasks[task_id_str] = final_task # Store using task_id_str

        if task_id_str in failed_tasks: # Check using task_id_str
            assert final_task.status == TaskStatus.FAILED, f"Task {task_id_str} polled as failed but DB status is {final_task.status}" # Use task_id_str
            print(f"Task {task_id_str} verified as FAILED in DB.") # Use task_id_str
        elif task_id_str in completed_tasks: # Check using task_id_str
            assert final_task.status == TaskStatus.COMPLETED, f"Task {task_id_str} polled as completed but DB status is {final_task.status}" # Use task_id_str
            assert final_task.output is not None
            assert isinstance(final_task.output, str)
            assert len(final_task.output) > 5 # Basic check
            print(f"Task {task_id_str} verified as COMPLETED in DB.") # Use task_id_str
        else:
            # This case should ideally not be reached if the polling loop logic is correct
             pytest.fail(f"Task {task_id_str} did not reach a known terminal state during polling but loop finished.") # Use task_id_str

    # Ensure all tasks either completed or failed as observed during polling
    assert len(completed_tasks) + len(failed_tasks) == num_tasks, "Mismatch between polled terminal states and total tasks."
    # For this specific test, we expect all to succeed ideally
    assert len(failed_tasks) == 0, f"One or more concurrent tasks failed: {failed_tasks}"
    assert len(completed_tasks) == num_tasks, f"Expected {num_tasks} completed tasks, but got {len(completed_tasks)}"

    print(f"All {num_tasks} concurrent tasks completed successfully and verified.")


# TODO: Add more test cases for different scenarios:
# - Tasks using different agent configurations (if applicable and supported by API)
# - Tasks involving tool use (if agentkit tools are integrated)
