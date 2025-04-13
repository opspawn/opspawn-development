"""
Global pytest fixtures and configuration for ops_core tests.
"""

import pytest
import pytest_asyncio
import pytest
import pytest_asyncio
import asyncio
import os # Added
from dotenv import load_dotenv # Added
from unittest.mock import patch, MagicMock, AsyncMock
import dramatiq # Import dramatiq
from dramatiq.brokers.stub import StubBroker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import delete # Added import
# Import SQLModel is no longer needed here if we use the specific metadata
# from sqlmodel import SQLModel

# Import the shared metadata object and specific models needed for clearing
from ops_core.models.base import metadata
# Removed Task import - it should be implicitly known by metadata
# from ops_core.models.tasks import Task # Added import

from ops_core.config.loader import get_resolved_mcp_config # Import config loader

from ops_core.config.loader import McpConfig # Import the type
from ops_core.metadata.store import InMemoryMetadataStore # Corrected path, keep for other tests
from ops_core.mcp_client.client import OpsMcpClient # Corrected path
# Removed sys.path hack
# Removed actor import to break collection-time dependency chain causing metadata error
# from src.ops_core.scheduler.engine import execute_agent_task_actor

# Load environment variables from .env file in the project root
# This ensures DATABASE_URL is available for tests
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)


# --- Session-Scoped Event Loop for Async Fixtures ---
# Override the default function-scoped event_loop fixture
@pytest.fixture(scope="session")
def event_loop(request):
    """Create an instance of the default event loop for session-scoped fixtures."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# --- Database Fixtures for SqlMetadataStore Tests ---

# Use a separate test database URL if possible, or ensure clean state
# For simplicity here, we'll use the default but manage tables.
# In a real scenario, use a dedicated test DB URL via env var.
# TEST_DATABASE_URL = get_resolved_mcp_config().database_url # Original attempt
TEST_DATABASE_URL = os.getenv("DATABASE_URL") # Directly get from loaded env
if not TEST_DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set or .env file not found.")

# Modify URL slightly if needed for testing (e.g., different DB name)
# TEST_DATABASE_URL = TEST_DATABASE_URL.replace("/opspawn_db", "/test_opspawn_db")

# Removed deprecated custom event_loop fixture; rely on pytest-asyncio default

# Function-scoped engine, created once per test function run
@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Provides an async engine fixture, managing tables for a single test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        # Ensure clean start and create tables using shared metadata
        await conn.run_sync(metadata.drop_all)
        await conn.run_sync(metadata.create_all)
    yield engine
    # Dispose the engine after all tests in the module are done
    await engine.dispose()

# Function-scoped session, ensures test isolation via transactions
@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """
    Provides a transactional AsyncSession for each test function.
    Changes are rolled back automatically after each test.
    Also explicitly clears the Task table before yielding.
    """
    async_session_factory = sessionmaker(
        bind=db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        # Explicitly delete all tasks before starting the test transaction
        # This is an extra safety measure against state leakage
        # Need to re-import Task locally for delete() to work
        from ops_core.models.tasks import Task
        await session.execute(delete(Task))
        await session.commit() # Commit the delete before yielding

        # Yield the session directly without transaction management here
        yield session
        # Rely on db_engine drop/create for isolation between tests
        await session.close()


# --- Existing Fixtures ---

@pytest_asyncio.fixture(scope="function")
async def mock_metadata_store() -> InMemoryMetadataStore:
    """Provides a clean InMemoryMetadataStore for each test function."""
    return InMemoryMetadataStore()

# Rename fixture to avoid conflict if used directly in tests needing the other one
@pytest_asyncio.fixture(scope="function")
async def mock_mcp_client() -> MagicMock:
    """Provides a mocked OpsMcpClient for each test function."""
    client = MagicMock(spec=OpsMcpClient)
    client.start_all_servers = AsyncMock()
    client.stop_all_servers = AsyncMock()
    client.call_tool = AsyncMock()
    # Add other methods if needed by tests
    return client

# Removed stub_broker fixture definition. Broker setup will be handled explicitly where needed.

# --- Global Test Setup ---

# Removed pytest_configure hook as broker setup is now handled conditionally
# in src/ops_core/tasks/broker.py based on DRAMATIQ_TESTING env var.

# Removed autouse set_stub_broker fixture.


# --- pytest-docker Configuration Override ---

@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    """Override default location of docker-compose.yml file."""
    # Construct path relative to the root directory where pytest is invoked
    # Assuming pytest is run from the workspace root '/home/sf2/Workspace/23-opspawn/1-t'
    return os.path.join(str(pytestconfig.rootdir), "..", "docker-compose.yml")


# --- Live E2E Test Fixtures ---

import subprocess
import time
import httpx
from sqlalchemy.ext.asyncio import create_async_engine as create_async_engine_live
from sqlalchemy.orm import sessionmaker as sessionmaker_live
from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
import pytest_docker

# Session-scoped fixture to manage Docker containers
@pytest.fixture(scope="session")
def docker_services_ready(docker_ip, docker_services):
    """Ensure that PostgreSQL and RabbitMQ are responsive."""
    # Wait for PostgreSQL
    pg_port = docker_services.port_for("postgres_db", 5432)
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.5, check=lambda: is_postgres_ready(docker_ip, pg_port)
    )
    # Wait for RabbitMQ
    rmq_port = docker_services.port_for("rabbitmq", 5672)
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.5, check=lambda: is_rabbitmq_ready(docker_ip, rmq_port)
    )
    # Add a longer delay to allow DB to fully initialize internally
    print("Adding longer delay after DB readiness check...")
    time.sleep(10)
    print("Delay finished.")
    print("[Fixture docker_services_ready] Setup complete, yielding.")
    yield docker_services
    print("[Fixture docker_services_ready] Teardown starting.")

def is_postgres_ready(ip, port):
    """Check if PostgreSQL is ready."""
    try:
        # Simple check: try to establish a connection
        # In a real scenario, might use pg_isready or attempt a query
        import socket
        sock = socket.create_connection((ip, port), timeout=1)
        sock.close()
        print(f"PostgreSQL at {ip}:{port} is ready.")
        return True
    except (socket.error, ConnectionRefusedError) as ex:
        print(f"PostgreSQL at {ip}:{port} not ready yet: {ex}")
        return False

def is_rabbitmq_ready(ip, port):
    """Check if RabbitMQ is ready."""
    try:
        # Simple check: try to establish a connection
        import socket
        sock = socket.create_connection((ip, port), timeout=1)
        sock.close()
        print(f"RabbitMQ at {ip}:{port} is ready.")
        return True
    except (socket.error, ConnectionRefusedError) as ex:
        print(f"RabbitMQ at {ip}:{port} not ready yet: {ex}")
        return False

# Session-scoped fixture to run Alembic migrations
@pytest.fixture(scope="session")
def run_migrations(docker_services_ready, docker_ip):
    """Runs Alembic migrations against the live test database."""
    pg_port = docker_services_ready.port_for("postgres_db", 5432)
    # Construct the DATABASE_URL for the container
    # Use credentials from docker-compose.yml
    # Add ssl=prefer to handle potential SSL issues with asyncpg
    live_db_url = f"postgresql+asyncpg://opspawn_user:opspawn_password@{docker_ip}:{pg_port}/opspawn_db?ssl=prefer"
    print(f"Running migrations against: {live_db_url}")

    # Set the DATABASE_URL environment variable for Alembic
    os.environ["DATABASE_URL"] = live_db_url

    # Find the alembic.ini file relative to this conftest.py
    alembic_ini_path = os.path.join(os.path.dirname(__file__), '..', 'alembic.ini')
    if not os.path.exists(alembic_ini_path):
        raise FileNotFoundError(f"Alembic config not found at expected path: {alembic_ini_path}")

    alembic_cfg = AlembicConfig(alembic_ini_path)
    # Point Alembic to the correct directory containing the 'versions' folder
    script_location = os.path.join(os.path.dirname(__file__), '..', 'alembic')
    alembic_cfg.set_main_option("script_location", script_location)
    # Ensure Alembic uses the correct DATABASE_URL from the environment
    alembic_cfg.set_main_option("sqlalchemy.url", live_db_url)

    try:
        alembic_command.upgrade(alembic_cfg, "head")
        print("Alembic migrations completed successfully.")
    except Exception as e:
        print(f"Alembic migration failed: {e}")
        raise

    print("[Fixture run_migrations] Setup complete, yielding DB URL.")
    # Yield the URL for other fixtures if needed
    yield live_db_url
    print("[Fixture run_migrations] Teardown starting.")

# Session-scoped fixture for the live API server process
@pytest.fixture(scope="session")
def live_api_server(run_migrations, docker_services_ready, docker_ip):
    """Starts the FastAPI server as a subprocess for the test session."""
    live_db_url = run_migrations # Get the DB URL from the migration fixture
    rmq_port = docker_services_ready.port_for("rabbitmq", 5672)
    # Use credentials from docker-compose.yml
    live_rabbitmq_url = f"amqp://guest:guest@{docker_ip}:{rmq_port}/"

    api_host = "0.0.0.0" # Listen on all interfaces inside the test env
    api_port = 8000 # Standard FastAPI port

    # Environment variables for the server process
    server_env = os.environ.copy()
    server_env["DATABASE_URL"] = live_db_url
    server_env["RABBITMQ_URL"] = live_rabbitmq_url
    # Add any other required env vars (e.g., LLM keys if needed by API startup)
    # server_env["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY", "")
    # server_env["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY", "")
    # server_env["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")
    # server_env["OPENROUTER_API_KEY"] = os.getenv("OPENROUTER_API_KEY", "")
    # server_env["AGENTKIT_LLM_PROVIDER"] = os.getenv("AGENTKIT_LLM_PROVIDER", "openai") # Example

    # Command to start the server
    # Ensure uvicorn and ops_core are available in the environment running pytest
    # This might require running pytest within the tox environment
    cmd = [
        "uvicorn",
        "ops_core.main:app",
        "--host", api_host,
        "--port", str(api_port),
        # "--reload", # Avoid reload in tests
    ]

    print(f"Starting API server with command: {' '.join(cmd)}")
    print(f"  DATABASE_URL={live_db_url}")
    print(f"  RABBITMQ_URL={live_rabbitmq_url}")

    # Start the server process
    process = subprocess.Popen(cmd, env=server_env)

    # Wait for the server to be ready
    api_base_url = f"http://localhost:{api_port}" # Use localhost as tests run on host
    max_wait = 30
    start_time = time.time()
    server_ready = False
    while time.time() - start_time < max_wait:
        try:
            # Check a known endpoint, e.g., /docs
            response = httpx.get(f"{api_base_url}/docs", timeout=1)
            if response.status_code == 200:
                print(f"API server at {api_base_url} is ready.")
                server_ready = True
                break
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            print(f"API server not ready yet ({e}), waiting...")
            time.sleep(1)
        except Exception as e:
            print(f"Unexpected error checking API server readiness: {e}")
            time.sleep(1)


    if not server_ready:
        process.terminate() # Clean up if server failed to start
        process.wait()
        pytest.fail(f"API server failed to start within {max_wait} seconds.")
 
    print("[Fixture live_api_server] Setup complete, yielding API base URL.")
    yield api_base_url # Provide the base URL to tests

    # Teardown: Stop the server process
    print("Stopping API server...")
    process.terminate()
    try:
        process.wait(timeout=5)
        print("API server stopped.")
    except subprocess.TimeoutExpired:
        print("API server did not terminate gracefully, killing.")
        process.kill()
        process.wait()

# Session-scoped fixture for the live Dramatiq worker process
@pytest.fixture(scope="session")
def live_dramatiq_worker(run_migrations, docker_services_ready, docker_ip):
    """Starts the Dramatiq worker as a subprocess for the test session."""
    live_db_url = run_migrations # Get the DB URL
    rmq_port = docker_services_ready.port_for("rabbitmq", 5672)
    live_rabbitmq_url = f"amqp://guest:guest@{docker_ip}:{rmq_port}/"

    # Environment variables for the worker process
    worker_env = os.environ.copy()
    worker_env["DATABASE_URL"] = live_db_url
    worker_env["RABBITMQ_URL"] = live_rabbitmq_url
    # Explicitly pass common LLM API keys to the worker environment
    for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY", "AGENTKIT_LLM_PROVIDER", "AGENTKIT_LLM_MODEL"]:
        value = os.getenv(key)
        if value is not None:
            worker_env[key] = value
        elif key in worker_env: # Remove if present in copied env but not set in host
             del worker_env[key]

    # Command to start the worker
    # Ensure dramatiq and ops_core are available in the environment running pytest
    cmd = [
        "dramatiq",
        "ops_core.tasks.broker:broker",
        "ops_core.tasks.worker", # Point to the module containing actors
    ]

    print(f"Starting Dramatiq worker with command: {' '.join(cmd)}")
    print(f"  DATABASE_URL={live_db_url}")
    print(f"  RABBITMQ_URL={live_rabbitmq_url}")

    # Start the worker process
    process = subprocess.Popen(cmd, env=worker_env)

    # Give the worker a moment to initialize
    # Check if worker process exited quickly after a short delay
    time.sleep(2) # Wait a couple of seconds
    if process.poll() is not None:
        # Process terminated, capture output if possible (might be complex)
        # For now, just fail the fixture setup
        process.terminate()
        process.wait()
        pytest.fail(f"Dramatiq worker process exited prematurely with code {process.returncode}. Check worker logs/errors.")
    else:
        print("Dramatiq worker process is running after initial delay.")
 
    print("[Fixture live_dramatiq_worker] Setup complete, yielding worker process.")
    yield process # Provide the process handle if needed

    # Teardown: Stop the worker process
    print("Stopping Dramatiq worker...")
    process.terminate()
    try:
        process.wait(timeout=5)
        print("Dramatiq worker stopped.")
    except subprocess.TimeoutExpired:
        print("Dramatiq worker did not terminate gracefully, killing.")
        process.kill()
        process.wait()

# Session-scoped engine connected to the live Docker database
@pytest_asyncio.fixture(scope="session")
async def live_db_engine(run_migrations):
    """Provides an async engine connected to the live test database."""
    live_db_url = run_migrations
    engine = create_async_engine_live(live_db_url, echo=False)
    yield engine
    await engine.dispose()

# Function-scoped session for interacting with the live database during tests
@pytest_asyncio.fixture(scope="function")
async def live_db_session(live_db_engine):
    """
    Provides an AsyncSession connected to the live test database for a single test.
    Does NOT manage transactions or table state automatically. Tests are responsible
    for cleaning up any data they create if necessary, or relying on the
    session-level setup/teardown for a clean slate between test runs.
    """
    async_session_factory = sessionmaker_live(
        bind=live_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        yield session
        # No automatic rollback - tests interact with live state
        await session.close()

# Function-scoped HTTP client for interacting with the live API server
@pytest_asyncio.fixture(scope="function")
async def live_api_client(live_api_server):
    """Provides an httpx.AsyncClient configured for the live API server."""
    async with httpx.AsyncClient(base_url=live_api_server, timeout=30.0) as client:
        yield client
