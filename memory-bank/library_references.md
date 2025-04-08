# Library References

This file contains links to documentation and version information for key external tools and libraries used in the Opspawn project.

## Asynchronous Task Queue

### Dramatiq
- **Official Documentation:** [https://dramatiq.io/](https://dramatiq.io/)
- **Latest Version (as of 2025-04-06):** 1.17.1 (from docs)
- **Python Support:** 3.9+
- **PyPI:** [https://pypi.org/project/dramatiq/](https://pypi.org/project/dramatiq/)
- **GitHub:** [https://github.com/Bogdanp/dramatiq](https://github.com/Bogdanp/dramatiq)

### RabbitMQ
- **Official Documentation:** [https://www.rabbitmq.com/docs](https://www.rabbitmq.com/docs)
- **Tutorials:** [https://www.rabbitmq.com/tutorials](https://www.rabbitmq.com/tutorials)
- **Python Tutorial:** [https://www.rabbitmq.com/tutorials/tutorial-one-python](https://www.rabbitmq.com/tutorials/tutorial-one-python)
- **Client Libraries:** [https://www.rabbitmq.com/client-libraries](https://www.rabbitmq.com/client-libraries)
- **Docker Image (used):** `rabbitmq:3-management` (includes management UI)

## Load Testing Tool

### Locust
- **Official Documentation:** [https://locust.io/](https://locust.io/)
- **Description:** An open-source load testing tool where user behavior is defined in Python code.
- **Key Features:** Scalable, event-based, supports distributed testing, web UI for monitoring.
- **PyPI:** [https://pypi.org/project/locust/](https://pypi.org/project/locust/)
- **GitHub:** [https://github.com/locustio/locust](https://github.com/locustio/locust)

## LLM SDKs (for Agentkit Integration)

### OpenAI
- **Official Documentation:** [https://platform.openai.com/docs/api-reference/introduction?lang=python](https://platform.openai.com/docs/api-reference/introduction?lang=python)
- **GitHub:** [https://github.com/openai/openai-python](https://github.com/openai/openai-python)
- **PyPI:** [https://pypi.org/project/openai/](https://pypi.org/project/openai/)

### Anthropic
- **Official Documentation:** [https://docs.anthropic.com/en/api/client-sdks](https://docs.anthropic.com/en/api/client-sdks)
- **GitHub:** [https://github.com/anthropics/anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python)
- **PyPI:** [https://pypi.org/project/anthropic/](https://pypi.org/project/anthropic/)

### Google Gemini (New SDK: google-genai)
- **Official Documentation:** [https://cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview](https://cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview)
- **GitHub:** [https://github.com/googleapis/python-genai](https://github.com/googleapis/python-genai)
- **PyPI:** [https://pypi.org/project/google-genai/](https://pypi.org/project/google-genai/)
- **Note:** Replaces the deprecated `google-generativeai` package.

### Google Gemini (Deprecated SDK: google-generativeai)
- **Status:** Deprecated as of ~April 2025. Use `google-genai` instead.
- **PyPI:** [https://pypi.org/project/google-generativeai/](https://pypi.org/project/google-generativeai/)
- **Known Issues:** Potential import errors related to protobuf versions (e.g., `AttributeError: module 'proto' has no attribute 'module'`).

### OpenRouter
- **Official Documentation:** [https://openrouter.ai/docs/quickstart](https://openrouter.ai/docs/quickstart)
- **Notes:** Uses OpenAI-compatible API structure. Can likely use the `openai` Python SDK with modified `base_url` and API key.
