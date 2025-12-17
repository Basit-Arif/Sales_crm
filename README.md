## Sales Distribution / Digital CEO CRM

This repository contains a **sales CRM and communication platform** with an optional **AI agent service**.  
It is designed to help teams capture leads, manage sales reps, chat with prospects across multiple channels, and generate AI-powered insights and summaries.

### Main components

- **`sales_crm/`**: Flask-based web application that provides:
  - Admin and sales rep dashboards
  - Lead management and distribution
  - Meeting scheduling and reminders
  - Real-time notifications and chat using Socket.IO
  - Integrations for WhatsApp, Instagram, and Messenger
  - Background jobs and reminders powered by Celery and Redis
- **`ai-agent/`**: FastAPI microservice that:
  - Uses OpenAI (via `openai-agents`) to understand lead messages
  - Extracts meeting intent, date, time, and timezone from free text
  - Generates short, focused summaries of conversations for CRM admins

## High-level architecture

- **Backend CRM (`sales_crm`)**
  - Flask + SQLAlchemy + Flask-Migrate
  - MySQL database (configured via `DATABASE_URL`)
  - Socket.IO for real-time events (e.g., new messages, notifications)
  - Celery workers for scheduled tasks and messaging workflows
  - Admin/user dashboards built with server‑rendered HTML templates
  - Routes grouped by area (auth, admin dashboard, user dashboard, messaging, webhooks, WhatsApp, Instagram, Messenger)

- **AI Agent (`ai-agent`)**
  - FastAPI service exposing endpoints such as:
    - `/process`: detect whether a message is about scheduling a meeting and extract structured details
    - `/summarize`: summarize a day’s conversation with a lead into concise bullet points
  - Uses tools (e.g., current-time lookup by timezone) to resolve relative dates like “tomorrow”
  - Intended to be called from the CRM or other services to enrich lead data and reports

- **Docker & supporting services**
  - `sales_crm/docker-compose.yml` defines:
    - `flask`: main CRM app (port `5005`)
    - `celery`: background worker
    - `ai-agent`: AI microservice (port `8000`)
    - `redis`: broker/backend for Celery and real-time features

## Features

- **Lead management**
  - Capture and manage leads
  - View detailed lead info, comments, and conversation history
  - Automatic or rule-based lead distribution (see `lead_distribution_logic.py`)

- **Dashboards**
  - **Admin dashboard**: manage users, companies, and sales reps; monitor activity
  - **Sales rep dashboard**: see assigned leads, conversations, and tasks

- **Messaging & channels**
  - Endpoints and services for:
    - **WhatsApp** (`whatsapp_services.py`)
    - **Instagram** (`instagram_services.py`)
    - **Messenger** (`massenger_services.py`)
  - Centralized message views and conversations inside the CRM

- **Meetings, reminders, and notifications**
  - Schedule and track meetings from the user dashboard
  - Automatic reminders via Celery tasks
  - Real-time notifications using Socket.IO rooms per user

- **AI assistance**
  - Detect meeting intent from free‑form lead messages
  - Normalize dates and times based on timezone
  - Generate concise, human‑readable summaries for admins

## Tech stack

- **Language**: Python 3.11
- **Web frameworks**: Flask (CRM), FastAPI (AI agent)
- **Database**: MySQL (via SQLAlchemy)
- **Background jobs**: Celery + Redis
- **Real-time**: Flask-SocketIO
- **AI**: OpenAI (via `openai-agents`)
- **Packaging / deps**: `uv`, `pyproject.toml` in each service
- **Containerization**: Docker + Docker Compose

## Running the project with Docker

- **Prerequisites**
  - Docker and Docker Compose installed
  - Two `.env` files configured:
    - `sales_crm/app/.env` (database, mail, Flask settings)
    - `ai-agent/.env` (e.g. `OPENAI_API_KEY` and any other required vars)

- **Steps**
  - **1. Start the stack**
    - From the `sales_crm` directory:
      - `docker-compose up --build`
  - **2. Services**
    - CRM web app: `http://localhost:5005`
    - AI agent: `http://localhost:8000`

## Running locally without Docker (development)

- **sales_crm (Flask app)**
  - Go to the folder:
    - `cd sales_crm`
  - Install dependencies (using `uv`):
    - `uv sync`
  - Configure environment:
    - Create `app/.env` with at least `DATABASE_URL`, mail settings, and any other required config
  - Run the app:
    - `uv run run.py`

- **ai-agent (FastAPI service)**
  - Go to the folder:
    - `cd ai-agent`
  - Install dependencies:
    - `uv sync`
  - Configure environment:
    - Create `.env` with `OPENAI_API_KEY` and any needed settings
  - Run the service:
    - `uv run main.py`
  - Access docs:
    - `http://localhost:8000/docs`

## Tests

- **sales_crm**
  - From `sales_crm`:
    - Ensure `TEST_DATABASE_URL` is set (see `pyproject.toml`)
    - Run tests:
      - `uv run pytest`

## Folder overview

- **`sales_crm/`**: main CRM application (Flask, Celery, Socket.IO, templates, static files, tests)
- **`ai-agent/`**: AI microservice (FastAPI, OpenAI integration)
- **`logs/`**: log files for various services
- **`testing/`**: auxiliary testing scripts (e.g. `testingapp.py`)

This README is a high-level guide; individual subfolders (`sales_crm`, `ai-agent`) can also have their own more detailed READMEs if needed.


