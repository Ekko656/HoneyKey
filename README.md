# HoneyKey Backend                                                                                                                       
  Minimal FastAPI backend for the HoneyKey hackathon demo. It logs suspicious traffic and groups honeypot key usage into incidents.     
  
  ## Quickstart

  ```bash
  python -m venv .venv
  source .venv/bin/activate   # Windows: .venv\Scripts\activate
  pip install -r requirements.txt
  cp .env.example .env
  uvicorn app.main:app --reload

  The service will auto-create the SQLite database at ./data/honeykey.db.

  Endpoints

  Health

  - GET /health → { "status": "ok" }

  Trap endpoints (return fake data when honeypot key is used)

  - GET /v1/projects
  - GET /v1/secrets
  - POST /v1/auth/verify

  Analyst endpoints

  - GET /incidents
  - GET /incidents/{id}
  - GET /incidents/{id}/events
  - POST /incidents/{id}/analyze
  - GET /incidents/{id}/ai-report

  IP Blocking

  - POST /incidents/{id}/block-ip
  - DELETE /incidents/{id}/unblock-ip
  - GET /blocklist
  - GET /blocklist/export?format=nginx

  Frontend API

  - GET /api/dashboard/stats
  - GET /api/reports
  - GET /api/reports/{id}
  - POST /api/reports/{id}/analyze

  Configuration

  Set values via environment variables or .env:

  DATABASE_PATH=./data/honeykey.db
  HONEYPOT_KEY=acme_live_f93k2jf92jf0s9df
  INCIDENT_WINDOW_MINUTES=30
  CORS_ORIGINS=http://localhost:5173,http://localhost:3000
  GEMINI_API_KEY=
  GEMINI_MODEL=gemini-1.5-pro

  Demo Honeypot Keys
  ┌──────────────────────────────┬────────────────────────────────────────────────────┐
  │             Key              │                  Attack Scenario                   │
  ├──────────────────────────────┼────────────────────────────────────────────────────┤
  │ acme_docker_j4k5l6m7n8o9p0q1 │ GitHub credential leak (exposed in docker-compose) │
  ├──────────────────────────────┼────────────────────────────────────────────────────┤
  │ acme_client_m5n6o7p8q9r0s1t2 │ Source map extraction (found in client JS)         │
  ├──────────────────────────────┼────────────────────────────────────────────────────┤
  │ acme_debug_a1b2c3d4e5f6g7h8  │ Debug log exposure (leaked in logs)                │
  └──────────────────────────────┴────────────────────────────────────────────────────┘
  Testing the Honeypot

  PowerShell (Windows)

  Scenario 1: GitHub Credential Leak
  $key = "acme_docker_j4k5l6m7n8o9p0q1"
  Write-Host "Attacker: Cloning private repositories..." -ForegroundColor Red
  curl.exe -s -H "Authorization: Bearer $key" "http://localhost:8000/v1/projects"

  Start-Sleep -Seconds 1
  $reports = curl.exe -s "http://localhost:8000/api/reports" | ConvertFrom-Json
  $id = $reports[0].incident_id
  Write-Host "HoneyKey: Detected Incident #$id" -ForegroundColor Green

  Write-Host "HoneyKey: Generating AI Report..." -ForegroundColor Cyan
  curl.exe -s -X POST "http://localhost:8000/incidents/$id/analyze"
  Write-Host "Success: Report ready on dashboard." -ForegroundColor Green

  Scenario 2: Source Map Extraction
  $key = "acme_client_m5n6o7p8q9r0s1t2"
  Write-Host "Attacker: Scraping API endpoints..." -ForegroundColor Red
  curl.exe -s -H "Authorization: Bearer $key" "http://localhost:8000/v1/projects"

  Start-Sleep -Seconds 1
  $reports = curl.exe -s "http://localhost:8000/api/reports" | ConvertFrom-Json
  $id = $reports[0].incident_id
  Write-Host "HoneyKey: Detected Incident #$id" -ForegroundColor Green

  Write-Host "HoneyKey: Generating AI Report..." -ForegroundColor Cyan
  curl.exe -s -X POST "http://localhost:8000/incidents/$id/analyze"
  Write-Host "Success: Report ready on dashboard." -ForegroundColor Green

  Scenario 3: Debug Log Compromise
  $key = "acme_debug_a1b2c3d4e5f6g7h8"
  Write-Host "Attacker: Accessing internal secrets vault..." -ForegroundColor Red
  curl.exe -s -H "Authorization: Bearer $key" "http://localhost:8000/v1/secrets"

  Start-Sleep -Seconds 1
  $reports = curl.exe -s "http://localhost:8000/api/reports" | ConvertFrom-Json
  $id = $reports[0].incident_id
  Write-Host "HoneyKey: Detected Incident #$id" -ForegroundColor Green

  Write-Host "HoneyKey: Generating AI Report..." -ForegroundColor Cyan
  curl.exe -s -X POST "http://localhost:8000/incidents/$id/analyze"
  Write-Host "Success: Report ready on dashboard." -ForegroundColor Green

  Bash (Linux/Mac)

  Scenario 1: GitHub Credential Leak
  KEY="acme_docker_j4k5l6m7n8o9p0q1"
  echo "Attacker: Cloning private repositories..."
  curl -s -H "Authorization: Bearer $KEY" "http://localhost:8000/v1/projects"

  sleep 1
  ID=$(curl -s "http://localhost:8000/api/reports" | jq '.[0].incident_id')
  echo "HoneyKey: Detected Incident #$ID"

  echo "HoneyKey: Generating AI Report..."
  curl -s -X POST "http://localhost:8000/incidents/$ID/analyze"
  echo "Success: Report ready on dashboard."

  Scenario 2: Source Map Extraction
  KEY="acme_client_m5n6o7p8q9r0s1t2"
  echo "Attacker: Scraping API endpoints..."
  curl -s -H "Authorization: Bearer $KEY" "http://localhost:8000/v1/projects"

  sleep 1
  ID=$(curl -s "http://localhost:8000/api/reports" | jq '.[0].incident_id')
  echo "HoneyKey: Detected Incident #$ID"

  echo "HoneyKey: Generating AI Report..."
  curl -s -X POST "http://localhost:8000/incidents/$ID/analyze"
  echo "Success: Report ready on dashboard."

  Scenario 3: Debug Log Compromise
  KEY="acme_debug_a1b2c3d4e5f6g7h8"
  echo "Attacker: Accessing internal secrets vault..."
  curl -s -H "Authorization: Bearer $KEY" "http://localhost:8000/v1/secrets"

  sleep 1
  ID=$(curl -s "http://localhost:8000/api/reports" | jq '.[0].incident_id')
  echo "HoneyKey: Detected Incident #$ID"

  echo "HoneyKey: Generating AI Report..."
  curl -s -X POST "http://localhost:8000/incidents/$ID/analyze"
  echo "Success: Report ready on dashboard."

  Unit Tests

  pytest
