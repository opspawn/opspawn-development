# Tech Context: Opspawn Core Foundation

## 1. Core Technologies

-   **Programming Language:** Python (Primary language for both `agentkit` and `ops-core`).
-   **Web Framework (for APIs):** FastAPI (Recommended for REST endpoints due to performance and type hinting integration).
-   **RPC Framework (Internal):** gRPC (Considered for high-performance internal communication between `ops-core` and `agentkit`, using Protocol Buffers).
-   **Asynchronous Programming:** `asyncio` (To be used extensively for non-blocking I/O, especially in `agentkit` for tool calls and potentially in `ops-core` for handling concurrent tasks).
-   **Data Validation:** Pydantic (Mandated by `.clinerules` for data validation, integrates well with FastAPI).

## 2. Data Storage

-   **Metadata Store (`ops-core`):** PostgreSQL or MySQL (Standard relational databases for storing workflow state, task history, etc.). Specific choice TBD.
-   **Long-Term Memory (`agentkit`):** Vector Databases (e.g., ChromaDB, Pinecone, Weaviate - specific choice TBD) for semantic search and retrieval. Potential for other persistent stores as needed.
-   **Short-Term Memory (`agentkit`):** In-memory storage, potentially simple data structures or libraries like Redis for caching.
-   **ORM/Database Interaction:** SQLAlchemy or SQLModel (Recommended by `.clinerules` if ORM is needed for the metadata store).

## 3. Development Environment & Tooling

-   **Version Control:** Git (Assumed, standard practice). Hosted on GitHub (Implied by `TASK.md` Task 1.1).
-   **Package Management:** `pip` with `pyproject.toml` (using `setuptools` backend) for defining dependencies and making packages installable (Implemented 2025-04-05).
-   **Testing Framework:** Pytest (Mandated by `.clinerules` for unit tests).
-   **Test Runner:** `tox` (Introduced 2025-04-05 for managing test environments, especially for inter-package dependencies like `ops-core` needing `agentkit`).
-   **Code Formatting:** Black (Mandated by `.clinerules`).
-   **Linting:** Flake8 or Ruff (Recommended for code quality, TBD).
-   **Type Checking:** Mypy (Recommended given the use of type hints).
-   **CI/CD:** GitHub Actions (Mentioned in `TASK.md` Task 1.2 for automated testing and documentation builds).
-   **Containerization:** Docker (Mentioned in `PLANNING.md` and research docs for deployment and potentially tool sandboxing).
-   **Container Orchestration:** Kubernetes (Mentioned in `PLANNING.md` as a target for scalable deployment).

## 4. Documentation Tools

-   **Framework:** Sphinx or MkDocs (Mandated by `.clinerules` and research docs). Decision between them TBD. Diátaxis framework recommended for structure.
-   **API Specification:** OpenAPI (for REST APIs), Protocol Buffers (for gRPC).
-   **Diagrams:** Mermaid or PlantUML (Recommended for embedding diagrams in Markdown).

## 5. Key Dependencies & Libraries (Anticipated)

-   **`agentkit`:** `pydantic`, `pytest`, `pytest-asyncio`. (LLM clients, vector DBs TBD).
-   **`ops-core`:** `pydantic`, `mcp`, `anthropic`, `python-dotenv`, `PyYAML`, `pytest`, `pytest-asyncio`. (FastAPI, DB drivers, ORM TBD).

## 6. Technical Constraints & Considerations

-   **Stateless Operation:** APIs should be designed to be stateless where possible (`PLANNING.md`).
-   **Security:** Sandboxing required for dynamic tool execution in `agentkit` (`PLANNING.md`, research docs). Access control considerations for APIs.
-   **Performance:** Balance between REST (ease of use) and gRPC (performance) for APIs. Optimize asynchronous operations.
-   **Code Length Limit:** No file should exceed 500 lines (`.clinerules`). Requires aggressive modularization.
-   **Python Focus:** Initial development is Python-centric. Cross-language support might be a future consideration (gRPC facilitates this).
-   **Non-Goals (Initial Phase):** Focus is on internal architecture and integration, not immediate packaging or complex deployment outputs (`PLANNING.md`).
