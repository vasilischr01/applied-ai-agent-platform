**# Applied AI Agent Platform**

Production-style local AI agent backend built with FastAPI, Ollama, semantic retrieval, tool execution, evaluation, observability, session memory, Docker, Kubernetes, pytest, Ruff, and GitHub Actions.

The project demonstrates applied AI engineering beyond a simple chatbot by combining tool orchestration, deterministic routing, local LLM inference, semantic document search, short-term conversational memory, evaluation, persistence, metrics, logging, performance optimization, containerization, and Kubernetes orchestration.

**---**

**## Why this project**

This is not only a chatbot.

The platform demonstrates how an AI-enabled backend can:

\- route requests to tools

\- bypass the LLM when deterministic logic is sufficient

\- execute tools safely

\- search local documents semantically

\- synthesize search results with a local LLM

\- preserve short-term conversational context

\- resolve follow-up questions across turns

\- persist agent runs

\- expose Prometheus metrics

\- measure latency by execution stage

\- evaluate tool selection and execution

\- run without a paid cloud LLM API

\- run as a containerized service

\- deploy to Kubernetes with health and readiness probes

The focus is on building reliable AI software with explicit engineering trade-offs.

**---**

**## Core features**

\- Local LLM through Ollama

\- Llama 3.2 3B support

\- Deterministic fast-path routing

\- LLM fallback routing for ambiguous requests

\- Safe calculator tool

\- Semantic document search

\- Sentence Transformer embeddings

\- Cached document embeddings

\- Database statistics tool

\- Session-based short-term conversation memory

\- Context-aware follow-up handling

\- Session reset endpoint

\- SQLite for local development

\- PostgreSQL support

\- SQLAlchemy persistence

\- Prometheus metrics

\- Structured logging

\- Per-stage latency instrumentation

\- Evaluation dataset and runner

\- FastAPI + Swagger

\- Docker / Docker Compose

\- Kubernetes deployment

\- Kubernetes ConfigMap

\- Kubernetes ClusterIP Service

\- Kubernetes Ingress manifest

\- Liveness and readiness probes

\- CPU and memory resource requests/limits

\- pytest + Ruff

\- GitHub Actions CI

\- Deterministic fallback behavior when Ollama is unavailable

**---**

**## Architecture**

\`\`\`text

Client

  |

  v

FastAPI

  |

  v

Agent Service

  |

  +-----------------------------+

  |                             |

  v                             v

Deterministic Router        LLM Planner

  |                             |

  +--------------+--------------+

                 |

                 v

             Tool Execution

                 |

        +--------+---------+

        |        |         |

        v        v         v

 Calculator  Document   Database

             Search      Stats

                 |

                 v

          Answer Generation

                 |

        +--------+---------+

        |                  |

        v                  v

 Deterministic         Ollama LLM

 Answer                Synthesis

        |

        v

 Session Memory

        |

        v

 Database + Metrics + Logs

\`\`\`

**### Deployment architecture**

\`\`\`text

Client

  |

  v

Kubernetes Service

  |

  v

Deployment

  |

  v

FastAPI Pod

  |

  +--> /health  -> liveness probe

  |

  +--> /ready   -> readiness probe

  |

  +--> Agent Service

         |

         +--> Tools

         +--> Database

         +--> Ollama

         +--> Prometheus Metrics

\`\`\`

**---**

**## Hybrid routing**

The agent uses a hybrid routing strategy.

For obvious requests, deterministic routing is used immediately.

Example:

\`\`\`text

What is 17.5 multiplied by 8?

\`\`\`

routes directly to:

\`\`\`text

calculator

\`\`\`

Another example:

\`\`\`text

Show me the database stats for previous runs.

\`\`\`

routes directly to:

\`\`\`text

database\_stats

\`\`\`

The LLM planner is only used when deterministic routing cannot confidently decide what to do.

This reduces:

\- unnecessary model calls

\- latency

\- compute usage

\- non-deterministic behavior

**---**

**## Local LLM integration**

The platform integrates with Ollama for local inference.

Default model:

\`\`\`text

llama3.2:3b

\`\`\`

The LLM is used for:

\- ambiguous tool routing

\- document-result synthesis

\- contextual follow-up answers

\- direct conversational reasoning

No paid cloud LLM API is required.

**---**

**## Semantic document search**

The document search tool uses dense embeddings instead of simple keyword matching.

Embedding model:

\`\`\`text

all-MiniLM-L6-v2

\`\`\`

The workflow is:

\`\`\`text

local text documents

        |

        v

Sentence Transformer embeddings

        |

        v

cached document vectors

        |

        v

query embedding

        |

        v

cosine similarity

        |

        v

ranked document results

\`\`\`

Example request:

\`\`\`json

{

  "message": "Find documents about monitoring model behavior."

}

\`\`\`

Example result:

\`\`\`json

{

  "document": "ml\_systems.txt",

  "score": 0.4551,

  "snippet": "..."

}

\`\`\`

**---**

**## Embedding cache**

Document embeddings are cached so they are not recomputed on every search request.

Without caching:

\`\`\`text

request

→ read documents

→ embed all documents

→ embed query

→ similarity search

\`\`\`

With caching:

\`\`\`text

startup

→ read documents

→ embed documents once

→ cache embeddings

request

→ embed query

→ similarity search

\`\`\`

This significantly reduces document-search overhead.

### Retrieval latency benchmark

The retrieval benchmark is implemented in:

```text
src/eval/retrieval_benchmark.py
```

Latest local result:

```text
queries_tested: 10
cold_start_ms: 13788.895

warm_latency_ms:
  average: 12.377
  median: 13.038
  p95: 13.566
  min: 10.030
  max: 13.655
```

The cold measurement includes one-time model initialization and corpus embedding in a fresh Python process. Warm requests reuse the initialized model and cached document embeddings. Results are hardware-dependent.

Machine-readable results are stored in:

```text
artifacts/retrieval_benchmark.json
```

**---**

**## Safe calculator**

Arithmetic expressions are evaluated using a restricted Python AST.

Supported operations include:

\- addition

\- subtraction

\- multiplication

\- division

\- powers

\- modulo

\- unary positive and negative values

The implementation avoids unsafe direct execution such as \`eval()\`.

Example:

\`\`\`json

{

  "message": "What is 17.5 multiplied by 8?"

}

\`\`\`

Result:

\`\`\`json

{

  "tool\_used": "calculator",

  "tool\_output": {

    "result": 140.0

  }

}

\`\`\`

**---**

**## Database statistics tool**

The agent can query aggregate statistics about previous runs.

Example request:

\`\`\`json

{

  "message": "Show me the database stats for previous runs."

}

\`\`\`

Example output:

\`\`\`json

{

  "total\_runs": 10,

  "tool\_runs": 8,

  "direct\_runs": 2

}

\`\`\`

**---**

**## Conversation memory**

The platform supports short-term session-based conversational memory.

Every request can include an optional:

\`\`\`text

session\_id

\`\`\`

If no session ID is supplied, the API generates one automatically.

Example first request:

\`\`\`json

{

  "message": "Find documents about monitoring model behavior."

}

\`\`\`

Example response:

\`\`\`json

{

  "session\_id": "6e5d01cd-f82f-4e71-b3db-b90740bfd6c8"

}

\`\`\`

A follow-up can reuse the same session:

\`\`\`json

{

  "message": "Summarize the first result.",

  "session\_id": "6e5d01cd-f82f-4e71-b3db-b90740bfd6c8"

}

\`\`\`

The agent can resolve references such as:

\`\`\`text

the first result

that result

that document

the previous result

it

\`\`\`

using stored conversation context.

**---**

**## Bounded short-term memory**

Conversation memory is intentionally bounded.

The in-memory session store limits:

\- the number of stored turns per session

\- the number of active sessions

This prevents uncontrolled context and memory growth.

The current memory implementation is intentionally local and process-bound.

**---**

**## Session reset**

A session can be cleared through:

\`\`\`text

DELETE /api/v1/sessions/{session\_id}

\`\`\`

Example response:

\`\`\`json

{

  "session\_id": "example-session-id",

  "cleared": true

}

\`\`\`

**---**

**## Tool-specific answer strategy**

Not every tool result requires another LLM call.

The platform uses deterministic final answers for simple tools such as:

\`\`\`text

calculator

database\_stats

\`\`\`

Document search can still use Ollama for natural-language synthesis.

This avoids paying the latency cost of a second model call when it adds no value.

**---**

**## Latency observability**

Agent execution is instrumented by stage.

The application measures:

\`\`\`text

planning\_ms

tool\_ms

answer\_generation\_ms

total\_ms

\`\`\`

Example:

\`\`\`text

planning\_ms: 0.15

tool\_ms: 46.38

answer\_generation\_ms: 26244.83

total\_ms: 26291.93

\`\`\`

This makes it possible to identify exactly where latency is introduced.

**---**

**## Performance optimization**

An earlier implementation used the local LLM for both planning and final answer generation.

Example measured latency:

\`\`\`text

planning\_ms: \~22782

tool\_ms: \~425

answer\_generation\_ms: \~15867

total\_ms: \~39076

\`\`\`

After introducing deterministic fast-path routing:

\`\`\`text

planning\_ms: \~0.15

tool\_ms: \~46

answer\_generation\_ms: \~26245

total\_ms: \~26292

\`\`\`

For simple deterministic tools, final LLM generation is skipped entirely.

Observed example:

\`\`\`text

calculator

planning\_ms: \~0.23

tool\_ms: \~0.04

answer\_generation\_ms: 0

total\_ms: \~0.34

\`\`\`

and:

\`\`\`text

database\_stats

planning\_ms: \~0.01

tool\_ms: \~5.2

answer\_generation\_ms: 0

total\_ms: \~5.26

\`\`\`

These measurements show the effect of eliminating unnecessary model calls.

**---**

**## Evaluation**

The project includes an evaluation endpoint:

\`\`\`text

POST /api/v1/eval/run

\`\`\`

The evaluation framework measures:

\- total cases

\- passed cases

\- pass rate

\- tool selection accuracy

\- tool execution accuracy

Example response:

\`\`\`json

{

  "total\_cases": 4,

  "passed\_cases": 4,

  "pass\_rate": 1.0,

  "tool\_selection\_accuracy": 1.0,

  "tool\_execution\_accuracy": 1.0

}

\`\`\`

The evaluation provides a reproducible way to validate agent behavior.

Latest deterministic evaluation (`ENABLE_LLM=false`):

```text
total_cases:              16
passed_cases:             16
pass_rate:                1.0
tool_selection_accuracy:  1.0
tool_execution_accuracy:  1.0
answer_validity_accuracy: 1.0
expected_result_accuracy: 1.0
output_schema_accuracy:   1.0
```

The deterministic mode is used for reproducible orchestration evaluation without LLM-output variability.

Machine-readable results are stored in:

```text
artifacts/agent_eval_results.json
```

**---**

**## Automated tests**

The project includes automated tests for:

\- health endpoint

\- readiness endpoint

\- calculator flow

\- semantic document-search flow

\- database-statistics flow

\- run history

\- session ID creation

\- session ID preservation

\- session memory storage

\- session deletion

\- unknown-session deletion

\- conversational follow-up behavior

\- tool behavior

\- evaluation behavior

\- memory-based follow-up with monkeypatching

Current test result:

\`\`\`text

27 passed

\`\`\`

Run:

\`\`\`powershell

pytest -q

\`\`\`

**---**

**## Linting**

The project uses Ruff.

Run:

\`\`\`powershell

ruff check .

\`\`\`

Automatic fixes:

\`\`\`powershell

ruff check . --fix

\`\`\`

Current status:

\`\`\`text

All checks passed!

\`\`\`

**---**

**## API endpoints**

**### Health**

\`\`\`text

GET /health

\`\`\`

Response:

\`\`\`json

{

  "status": "ok"

}

\`\`\`

**---**

**### Readiness**

\`\`\`text

GET /ready

\`\`\`

Response:

\`\`\`json

{

  "status": "ready"

}

\`\`\`

**---**

**### Run agent**

\`\`\`text

POST /api/v1/agent/run

\`\`\`

Example:

\`\`\`json

{

  "message": "Find documents about monitoring model behavior."

}

\`\`\`

Optional session-based request:

\`\`\`json

{

  "message": "Summarize the first result.",

  "session\_id": "example-session-id"

}

\`\`\`

Example response structure:

\`\`\`json

{

  "run\_id": "uuid",

  "session\_id": "uuid",

  "answer": "string",

  "tool\_used": "document\_search",

  "tool\_input": {},

  "tool\_output": {},

  "latency\_ms": 1000

}

\`\`\`

**---**

**### List agent runs**

\`\`\`text

GET /api/v1/agent/runs

\`\`\`

Optional limit:

\`\`\`text

GET /api/v1/agent/runs?limit=50

\`\`\`

**---**

**### Get agent run**

\`\`\`text

GET /api/v1/agent/runs/{run\_id}

\`\`\`

**---**

**### Clear session**

\`\`\`text

DELETE /api/v1/sessions/{session\_id}

\`\`\`

**---**

**### Run evaluation**

\`\`\`text

POST /api/v1/eval/run

\`\`\`

**---**

**### Prometheus metrics**

\`\`\`text

GET /metrics

\`\`\`

**---**

**## Observability**

The application exposes Prometheus-compatible metrics.

Metrics include:

\`\`\`text

agent\_runs\_total

agent\_tool\_calls\_total

agent\_run\_latency\_seconds

agent\_errors\_total

\`\`\`

A live Docker Compose workload also validated the Prometheus instrumentation.

Observed application metrics:

```text
agent_runs_total{status="success"} 5.0
agent_tool_calls_total{tool="calculator"} 2.0
agent_tool_calls_total{tool="document_search"} 2.0
agent_tool_calls_total{tool="database_stats"} 1.0
agent_run_latency_seconds_count 5.0
agent_run_latency_seconds_sum 163.01753908199998
```

This is an observability validation snapshot, not a throughput benchmark; the sample is small and includes cold model/LLM overhead.

Agent execution is also emitted through structured logging.

Example log fields:

\`\`\`text

run\_id

tool\_used

planning\_ms

tool\_ms

answer\_generation\_ms

total\_ms

\`\`\`

**---**

**## Persistence**

Agent runs are stored using SQLAlchemy.

Stored fields include:

\- run ID

\- user message

\- generated answer

\- selected tool

\- tool input

\- tool output

\- execution latency

\- success status

\- creation timestamp

SQLite is used for lightweight local development.

PostgreSQL is supported for production-style deployments.

**---**

**## Project structure**

\`\`\`text

applied-ai-agent-platform/

├── .github/

│   └── workflows/

│       └── ci.yml

├── artifacts/
│   ├── agent_eval_results.json
│   └── retrieval_benchmark.json
├── data/

│   ├── documents/

│   └── eval/

│       └── agent\_eval.json

├── src/

│   ├── agent/

│   │   ├── memory.py

│   │   ├── planner.py

│   │   ├── service.py

│   │   └── tools.py

│   ├── api/

│   │   └── main.py

│   ├── core/

│   │   ├── config.py

│   │   ├── logging.py

│   │   └── metrics.py

│   ├── db/

│   │   ├── base.py

│   │   └── session.py

│   ├── eval/

│   │   └── runner.py

│   ├── models/

│   │   └── run.py

│   └── schemas/

│       └── agent.py

├── k8s/

│   ├── configmap.yaml

│   ├── deployment.yaml

│   ├── ingress.yaml

│   └── service.yaml

├── tests/

│   ├── conftest.py

│   ├── test\_api.py

│   ├── test\_eval.py

│   └── test\_tools.py

├── .dockerignore

├── .env.example

├── .gitignore

├── docker-compose.yml

├── Dockerfile

├── LICENSE

├── pyproject.toml

├── README.md

└── requirements.txt

\`\`\`

**---**

**## Tech stack**

**### Backend**

\`\`\`text

Python

FastAPI

Pydantic

SQLAlchemy

Uvicorn

\`\`\`

**### AI / ML**

\`\`\`text

Ollama

Llama 3.2

Sentence Transformers

all-MiniLM-L6-v2

PyTorch

\`\`\`

**### Observability**

\`\`\`text

Prometheus

Structured logging

Latency instrumentation

\`\`\`

**### Quality**

\`\`\`text

pytest

Ruff

\`\`\`

**### Infrastructure**

\`\`\`text

Docker

Docker Compose

Kubernetes

GitHub Actions

PostgreSQL

SQLite

\`\`\`

**---**

**## Local setup**

**### 1. Create a virtual environment**

Windows:

\`\`\`powershell

python -m venv .venv

.\\.venv\Scripts\Activate.ps1

\`\`\`

**### 2. Install dependencies**

\`\`\`powershell

pip install -r requirements.txt

\`\`\`

**### 3. Environment configuration**

Copy:

\`\`\`text

.env.example

\`\`\`

to:

\`\`\`text

.env

\`\`\`

The real \`.env\` file is ignored by Git.

**---**

**## Ollama setup**

Install Ollama separately.

Verify:

\`\`\`powershell

ollama --version

\`\`\`

Pull the model:

\`\`\`powershell

ollama pull llama3.2:3b

\`\`\`

Test it:

\`\`\`powershell

ollama run llama3.2:3b

\`\`\`

Example:

\`\`\`text

\>>> Say only: model works

model works

\`\`\`

Exit with:

\`\`\`text

/bye

\`\`\`

**---**

**## Run the API**

\`\`\`powershell

uvicorn src.api.main\:app --reload

\`\`\`

Local API:

\`\`\`text

http\://127.0.0.1:8000

\`\`\`

Swagger:

\`\`\`text

http\://127.0.0.1:8000/docs

\`\`\`

Prometheus metrics:

\`\`\`text

http\://127.0.0.1:8000/metrics

\`\`\`

**---**

**## Example requests**

**### Calculator**

\`\`\`json

{

  "message": "What is 17.5 multiplied by 8?"

}

\`\`\`

**---**

**### Semantic document search**

\`\`\`json

{

  "message": "Find documents about monitoring model behavior."

}

\`\`\`

**---**

**### Database statistics**

\`\`\`json

{

  "message": "Show me the database stats for previous runs."

}

\`\`\`

**---**

**### Follow-up conversation**

First request:

\`\`\`json

{

  "message": "Find documents about monitoring model behavior."

}

\`\`\`

Take the returned:

\`\`\`text

session\_id

\`\`\`

Then send:

\`\`\`json

{

  "message": "Summarize the first result.",

  "session\_id": "returned-session-id"

}

\`\`\`

**---**

**## Docker**

Docker Compose can start the FastAPI application and PostgreSQL. The PostgreSQL password is supplied through an environment variable.

Ollama is expected to run on the host machine because local model and GPU environments vary.

Run:

\`\`\`powershell

$env:POSTGRES_PASSWORD="postgres"

docker compose up --build

\`\`\`

**### Docker image**

A standalone application image can be built with:

\`\`\`powershell

docker build -t applied-ai-agent-platform\:latest .

\`\`\`

The repository includes a \`.dockerignore\` to prevent unnecessary local files such as virtual environments, Git metadata, caches, environment files, and local databases from being copied into the build context.

**---**

**## Kubernetes Deployment**

The application includes Kubernetes manifests for container orchestration and local cluster deployment.

\`\`\`text

k8s/

├── configmap.yaml

├── deployment.yaml

├── service.yaml

└── ingress.yaml

\`\`\`

**### Kubernetes components**

The Kubernetes configuration includes:

\- \`Deployment\` for application lifecycle management

\- \`ClusterIP Service\` for internal service discovery and routing

\- \`ConfigMap\` for application configuration

\- \`Ingress\` manifest for hostname-based routing

\- liveness probe using \`/health\`

\- readiness probe using \`/ready\`

\- CPU requests and limits

\- memory requests and limits

\- configurable container image pull policy

**### Build the image**

\`\`\`powershell

docker build -t applied-ai-agent-platform\:latest .

\`\`\`

**### Deploy**

\`\`\`powershell

kubectl apply -f k8s/configmap.yaml

kubectl apply -f k8s/deployment.yaml

kubectl apply -f k8s/service.yaml

kubectl apply -f k8s/ingress.yaml

\`\`\`

**### Verify the cluster**

\`\`\`powershell

kubectl cluster-info

kubectl get nodes

\`\`\`

**### Verify application resources**

\`\`\`powershell

kubectl get pods

kubectl get svc

kubectl get ingress

\`\`\`

A healthy application pod should report:

\`\`\`text

READY   STATUS

1/1     Running

\`\`\`

**### Local access**

For local development, expose the Kubernetes Service through port forwarding:

\`\`\`powershell

kubectl port-forward service/applied-ai-agent-service 8080:80

\`\`\`

Swagger is then available at:

\`\`\`text

http\://127.0.0.1:8080/docs

\`\`\`

Health endpoint:

\`\`\`text

http\://127.0.0.1:8080/health

\`\`\`

Expected response:

\`\`\`json

{

  "status": "ok"

}

\`\`\`

**### Health probes**

The Kubernetes Deployment uses:

\`\`\`text

GET /health

\`\`\`

as the liveness probe and:

\`\`\`text

GET /ready

\`\`\`

as the readiness probe.

This allows Kubernetes to distinguish between:

\- a container that is alive

\- an application that is ready to receive traffic

**### ConfigMap**

Runtime configuration is provided through:

\`\`\`text

k8s/configmap.yaml

\`\`\`

This separates deployment configuration from application code.

**### Resource management**

The Deployment defines CPU and memory requests and limits.

This provides explicit scheduling and resource boundaries instead of allowing the application container to consume unlimited cluster resources.

**### Service**

The application is exposed internally through:

\`\`\`text

applied-ai-agent-service

\`\`\`

using a Kubernetes \`ClusterIP\` Service.

The service maps:

\`\`\`text

port 80

→

container port 8000

\`\`\`

**### Ingress**

The included Ingress manifest defines the hostname:

\`\`\`text

applied-ai-agent.local

\`\`\`

An ingress controller is required for direct hostname-based routing.

The Ingress manifest is included as part of the deployment configuration even when local development uses \`kubectl port-forward\`.

**### Local validation**

The Kubernetes deployment was validated locally using Docker Desktop Kubernetes.

The validated flow was:

\`\`\`text

Docker image

    |

    v

Kubernetes Deployment

    |

    v

Pod

    |

    v

ClusterIP Service

    |

    v

kubectl port-forward

    |

    v

FastAPI /health and /docs

\`\`\`

The deployment successfully served both the health endpoint and Swagger documentation through the Kubernetes Service.

**---**

**## Security**

The project avoids executing arbitrary user code.

The calculator uses a restricted AST evaluator.

Sensitive and local-development files are excluded from Git.

Examples include:

\`\`\`text

.env

.venv/

\_\_pycache\_\_/

.pytest\_cache/

.ruff\_cache/

local database files

\`\`\`

Docker build context exclusions are managed through \`.dockerignore\`.

No API keys need to be committed to the repository.

Additional API hardening includes:

- sanitized client-facing error messages
- `503` handling for database/readiness failures
- 64 KiB request-size limit
- in-memory rate limiting at 60 requests per 60 seconds per client IP
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- restrictive `Permissions-Policy`
- `Cache-Control: no-store`
- PostgreSQL password supplied through environment configuration rather than hard-coded in Compose

The in-memory rate limiter is suitable for local/demo single-instance deployment. A distributed deployment should use a shared store, ingress controller, or API gateway for rate limiting.

**---**

**## Design decisions**

**### Local-first AI**

The application uses Ollama instead of requiring a paid cloud LLM API.

Benefits:

\- no per-request cloud API cost

\- local experimentation

\- local data processing

\- reproducible model configuration

\- easier offline development

**---**

**### Deterministic fast paths**

Simple requests should not require an LLM.

The system therefore combines:

\`\`\`text

deterministic routing

\+

LLM fallback

\`\`\`

This reduces latency and improves predictability.

**---**

**### Semantic retrieval**

Document search uses vector embeddings rather than relying only on literal keyword overlap.

This allows related concepts to be retrieved even when the exact wording differs.

**---**

**### Bounded memory**

Conversation memory is intentionally limited.

This prevents:

\- uncontrolled prompt growth

\- excessive process memory usage

\- continuously increasing context size

**---**

**### Observable execution**

The agent is treated as an observable software system rather than a black box.

Latency is measured separately for:

\`\`\`text

planning

tool execution

answer generation

total execution

\`\`\`

**---**

**### Containerized deployment**

Docker is used to package the application into a reproducible runtime environment.

A \`.dockerignore\` reduces unnecessary build context and excludes local development artifacts from the image build.

**---**

**### Kubernetes orchestration**

Kubernetes provides a deployment layer around the containerized application.

The implementation includes:

\- declarative deployment manifests

\- service discovery

\- configuration management

\- health monitoring

\- readiness monitoring

\- resource constraints

\- ingress configuration

This separates application code from runtime orchestration.

**---**

**## Current limitations**

The current implementation intentionally remains lightweight.

Current limitations include:

\- conversation memory is in-process

\- conversation memory is lost after application restart

\- session state is not distributed between multiple replicas

\- document search currently targets local text files

\- the local LLM can be slow on CPU

\- no authentication layer is currently included

\- no persistent vector database is required yet

\- inference speed depends heavily on hardware

\- Ollama is expected to run outside the Kubernetes pod in the current local configuration

\- direct Ingress routing requires an ingress controller

\- distributed session state would be required before safely scaling multiple application replicas

**---**

**## Future improvements**

Potential extensions include:

\- persistent Redis-backed conversation memory

\- distributed session state

\- document chunking

\- hybrid lexical + semantic retrieval

\- reranking

\- persistent vector database integration

\- streaming responses

\- asynchronous tool execution

\- response caching

\- OpenTelemetry tracing

\- Grafana dashboards

\- authentication and RBAC


\- model routing

\- prompt versioning

\- persistent evaluation history

\- retrieval-specific evaluation metrics

\- multi-step tool execution

\- native tool-calling model support

\- multi-agent workflows

\- Horizontal Pod Autoscaling

\- Kubernetes Secrets

\- Helm charts

\- cloud Kubernetes deployment

\- GPU inference support

**---**

**## Testing philosophy**

Tests are designed to avoid dependencies on external services where possible.

The automated suite does not require a live Ollama instance for core API and memory-flow validation.

Monkeypatching is used for conversational follow-up tests so the CI pipeline can verify session behavior deterministically.

**---**

**## CI**

GitHub Actions can automatically run quality checks on pushes and pull requests.

Typical CI checks include:

\`\`\`text

dependency installation

Ruff linting

pytest

\`\`\`

This helps prevent regressions before changes are merged.

**---**

**## What this project demonstrates**

The project combines several applied AI engineering areas in a single backend:

\`\`\`text

LLM orchestration

deterministic routing

semantic retrieval

tool execution

conversation memory

evaluation

API engineering

database persistence

observability

performance optimization

testing

containerization

Kubernetes orchestration

CI

\`\`\`

The goal is to demonstrate how AI capabilities can be integrated into a measurable, testable, deployable, and production-oriented software system.

**---**

**## License**

MIT License.