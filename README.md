# ADK-eCombat 🛒🤖

Welcome! This project is a multi-agent e-commerce customer support assistant powered by the **Google Agent Development Kit (ADK)**. It uses a PostgreSQL database for catalog search, orders, and session logging, and connects to LLM models via LiteLLM/OpenRouter.

Here is a step-by-step guide to get everything up and running.

---

## 📋 Prerequisites

Before starting, make sure you have the following installed on your machine:
1. **Python** (version 3.10 or newer)
2. **Docker** and **Docker Compose**
3. An **OpenRouter API Key** (or another LLM provider key)

---

## 🚀 Step-by-Step Setup

### 1. Configure Environment Variables
Copy or modify the environment file inside the `eCombat` folder to configure your API keys.
- Open the [eCombat/.env](file:///Users/vva049/Projects/MyWorks/ADK-eCombat/eCombat/.env) file.
- Add/update your OpenRouter API Key:
  ```env
  OPENROUTER_API_KEY=your_actual_api_key_here
  ```

---

### 2. Set Up Python Virtual Environment
It is best practice in Python to use a virtual environment (`venv`) to keep project dependencies isolated.

1. **Create the virtual environment**:
   ```bash
   python -m venv .venv
   ```
2. **Install all required dependencies**:
   ```bash
   .venv/bin/pip install -r requirements.txt
   ```

---

### 3. Spin Up the Database (Docker)
We use Docker to run a PostgreSQL database container. It will automatically load the database schema and seed sample products/orders when it first starts.

1. **Start the database container**:
   ```bash
   docker compose up -d
   ```
   *The `-d` flag runs the container in "detached" mode (in the background).*

2. **How to Reset / Re-initialize the Database**:
   If you ever want to wipe the database and start fresh with the seed data, run:
   ```bash
   docker compose down -v
   docker compose up -d
   ```
   *The `-v` flag removes the persistent database volume, forcing PostgreSQL to re-run the initialization script ([scripts/init_db.sql](file:///Users/vva049/Projects/MyWorks/ADK-eCombat/scripts/init_db.sql)).*

---

## 🏃‍♂️ Running the Agent

You can interact with your ADK agent in two ways: through the Terminal or a Web UI.

### Option A: Interactive CLI Mode (Terminal)
To start a conversation with the agent directly in your command line, run:
```bash
.venv/bin/adk run eCombat
```
Once loaded, type your message and press **Enter**. To exit, press `Ctrl + C` or type exit commands.

To send a single quick query without entering interactive mode:
```bash
.venv/bin/adk run eCombat "Hello"
```

### Option B: Interactive Web UI Mode (Recommended)
ADK comes with a built-in FastAPI web server that provides a clean, modern web interface.

1. **Start the web server**:
   ```bash
   .venv/bin/adk web eCombat
   ```
2. Open your browser and navigate to:
   ```
   http://127.0.0.1:8000
   ```
   Here you can interact with the agent, view execution traces, inspect tool calls, and debug interactions in real time!

---

## 📂 Project Structure

- **`eCombat/`**: The core application module.
  - [eCombat/src/agents/](file:///Users/vva049/Projects/MyWorks/ADK-eCombat/eCombat/src/agents/): Contains agent definitions (for example, `support_agent.py`, `sales_agent.py`, `ecombat_agent.py`).
  - [eCombat/src/tools/db_tools.py](file:///Users/vva049/Projects/MyWorks/ADK-eCombat/eCombat/src/tools/db_tools.py): Python functions exposed as tools to the agent (e.g., searching products, placing orders, logging sessions).
  - [eCombat/src/config/settings.py](file:///Users/vva049/Projects/MyWorks/ADK-eCombat/eCombat/src/config/settings.py): LLM model configurations.
- **`scripts/init_db.sql`**: SQL commands to create database tables and insert initial mock data.
- **`docker-compose.yml`**: Docker services config for the Postgres container.
- **`requirements.txt`**: List of Python package dependencies.