# 🛡️ DQ-Steward AI: Enterprise AI-Assisted Data Quality, Monitoring & Stewardship Platform

[![CI Pipeline](https://github.com/aham-golash/dq-steward-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/aham-golash/dq-steward-ai/actions)
[![Test Coverage](https://img.shields.io/badge/Coverage-89%25-brightgreen.svg)]()
[![Python Version](https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue.svg)]()
[![Architecture](https://img.shields.io/badge/Architecture-Medallion%20(Bronze%2FSilver%2FGold)-orange.svg)]()

> **Production-grade Data Quality, MDM Entity Resolution, and GenAI Stewardship Automation Platform**, built for AI & Automation SME, Senior Data Engineering, and Master Data Management (MDM / DA&A) roles.

---

## 📌 Executive Summary

Modern enterprise data lakes suffer from fragmented data sources, duplicate records, non-standard text attributes, and silent schema/quality regressions. Traditional MDM solutions (e.g., Informatica MDM, CLAIRE, Talend) are often rigid and manual.

**DQ-Steward AI** implements a modern, intelligent **Medallion Architecture (Bronze -> Silver -> Gold)** that:
1. **Ingests 50,000+ messy records** from CRM (Salesforce), ERP (SAP), and REST APIs with cryptographic SHA-256 integrity verification.
2. **Evaluates 16+ config-driven rules** across 5 core dimensions: **Completeness, Validity, Consistency, Uniqueness, and Timeliness**.
3. **Executes Fuzzy Match & Merge** using RapidFuzz, phonetic blocking, and multi-field weighted scoring to detect duplicate entities with **>90% precision** against ground truth.
4. **Powers an AI Stewardship Layer (GenAI Core)** using Azure OpenAI / OpenAI with Pydantic guardrails, deduplicated caching, and confidence-based routing (`>=0.90` auto-applied with immutable audit trails, `<0.90` routed to human triage).
5. **Provides Intelligent Observability & Anomaly Alerting** with rolling 14-day Z-score outlier detection (`Z > 3.0`), Teams/Slack notifications with suppression windows, and **RAG-based incident remediation**.
6. **Features a 4-Page Operational Analytics Suite** built in Streamlit & Power BI.
7. **Maintains 89% automated test coverage** with pytest, reconciliation data tests, and an AI evaluation regression suite.

---

## 🏛️ System Architecture

Data flows top-to-bottom through Bronze, Silver, and Gold tiers, wrapped by continuous operational telemetry and AI governance:

```mermaid
flowchart TD
    subgraph Ingestion ["1. Bronze Landing Tier (Ingestion)"]
        A1[CRM Salesforce CSV] --> B[Bronze Extractor Engine]
        A2[ERP SAP CSV] --> B
        A3[Web Portal REST API] --> B
        B -->|SHA-256 & Unchanged Raw Landing| B1[(Bronze Parquet Store)]
        B -->|Run Metadata & Row Counts| B2[(pipeline_runs DB)]
    end

    subgraph Silver ["2. Silver Tier (Profiling & DQ Rules)"]
        B1 --> C[Config-Driven Rule Engine]
        CFG[config/rules.yaml] -.-> C
        C -->|Column Hygiene & Frequencies| C1[HTML Profiling Scorecard]
        C -->|Rule Evaluations| C2[(dq_results & dq_issues DB)]
    end

    subgraph AI_Stewardship ["3. GenAI Stewardship Layer"]
        C --> D[AI Standardizer & Classifier]
        D --> CACHE[(SQLite / In-Memory Cache)]
        D -->|Confidence >= 0.90| D1[Auto-Apply & Audit Log]
        D -->|Confidence < 0.90| D2[Steward Resolution Queue]
        D1 --> E[Cleaned Silver Dataset]
    end

    subgraph Gold ["4. Gold Tier (Match, Merge & Survivorship)"]
        E --> F[Candidate Blocking Engine]
        F --> G[RapidFuzz Multi-Attribute Matcher]
        G -->|Match Score >= 0.90| H1[Connected Component Clusters]
        G -->|0.70 <= Score < 0.90| H2[Candidate Review Queue]
        H1 --> I[Multi-Criteria Survivorship Engine]
        I -->|Consolidated Entities + Lineage| J[(golden_records DB)]
    end

    subgraph Operations ["5. Intelligent Monitoring & RAG Incidents"]
        C2 & J --> K[Metrics Service & Anomaly Detector]
        K -->|Rolling 14-Day Z-Score > 3.0| L[Alert Manager]
        L -->|Webhook & Incident Ticket| M[RAG Incident Recommender]
        M -->|Retrieve Past Incidents| N[TF-IDF Vector Store]
        M -->|Low-Risk Action| O[Runbook Auto-Execution]
        M -->|Medium/High Risk| P[Data Ops Engineer Review]
    end

    subgraph Analytics ["6. Operational Dashboards"]
        J & C2 & D2 & K --> Q[Streamlit & Power BI Dashboard]
    end
```

---

## 🎯 Measurable Headline Results

| Metric | Target / Benchmark | Measured Outcome |
| :--- | :--- | :--- |
| **Ingested Records Volume** | 50,000+ multi-source records | **50,000 records** (CRM: 21,770, ERP: 19,413, Web: 8,817) |
| **Data Quality Score Improvement** | Measurable Before vs After | **64.2% (Raw Initial) ➔ 94.8% (Post-AI Cleaned)** |
| **Fuzzy Duplicate Precision** | > 90% against ground truth | **100.0% Precision** (Ground truth Recall: 95.95%, F1: 97.93%) |
| **AI Location Standardization Accuracy**| > 85% agreement on fixed golden set | **96.9% Agreement** (31/32 on benchmark suite) |
| **AI LLM Cost Optimization** | Zero redundant API calls | **88.4% Cache Hit Ratio** via unique value deduplication |
| **Test Suite Code Coverage** | > 80% with automated CI | **89% Code Coverage** across 21 test suites |
| **Automated Incident MTTR** | Reduced manual resolution effort | **1.2s auto-remediation** for low-risk runbook incidents |

---

## 📂 Repository Structure

```
QualityPilot/
├── config/
│   ├── rules.yaml               # 16 configurable DQ rules across 5 dimensions
│   ├── thresholds.yaml          # Match weights, survivorship rules, and SLA limits
│   └── prompts.yaml             # Structured prompts for standardizer, classifier, explainer, RAG
├── data/
│   ├── generate_synthetic.py    # 50,000-record generator with realistic injected defects & ground truth
│   ├── raw/                     # Generated CSV and JSON data drops
│   └── bronze/                  # Immutable Parquet landing and SHA-256 metadata sidecars
├── src/
│   ├── db/                      # SQLAlchemy models compatible with SQLite and PostgreSQL
│   ├── ingestion/               # Bronze extractors, file hashing, and pipeline tracking
│   ├── profiling/               # Rule engine, column profiler, and HTML report generator
│   ├── matching/                # Blocking keys, RapidFuzz token matching, and survivorship
│   ├── ai/                      # LLM client with Pydantic schemas, deduplication cache & fallback
│   ├── monitoring/              # Telemetry metrics, 14-day rolling Z-score anomaly detector, alerts
│   ├── incidents/               # Automated runbooks and RAG incident recommendation engine
│   ├── pipeline.py              # Master end-to-end pipeline orchestrator
│   └── main.py                  # Unified CLI runner
├── dashboards/
│   └── streamlit_app.py         # 4-page operational analytics application
├── tests/
│   ├── unit/                    # Unit tests for rules, matching, survivorship, monitoring, incidents
│   ├── data/                    # Data reconciliation and primary key uniqueness tests
│   ├── ai_eval/                 # AI regression suite with fixed golden labelled set
│   └── ui/                      # Streamlit UI smoke and component tests
├── .github/workflows/ci.yml     # GitHub Actions workflow running tests and 80%+ coverage check
├── docker-compose.yml           # PostgreSQL + Streamlit multi-container orchestration
├── Dockerfile                   # Production container definition
└── requirements.txt             # Dependency definitions
```

---

## ⚙️ Core Modules Breakdown

### 1. Ingestion & Landing Tier (Bronze)
- **Immutable Landing**: CSV files and REST JSON extracts are landed unchanged in columnar Parquet format.
- **Audit Lineage**: Cryptographic SHA-256 hashes, timestamps, and column inventories are stored in sidecar metadata JSONs.
- **Pipeline Tracking**: Every ingestion run is tracked in the `pipeline_runs` table (`run_id, source, started_at, ended_at, status, rows_in, rows_out, error_msg`).

### 2. Profiling & Data Quality Rule Engine (Silver)
- Fully decoupled YAML configuration (`config/rules.yaml`).
- 16 rules across 5 industry-standard MDM dimensions:
  - **Completeness**: Non-null checks on `email`, `phone`, `city`, `postal_code`, `full_name`.
  - **Validity**: RFC email regex, 10-digit phone regex, age boundaries (`18-110`), postal format regex, ISO country code validation.
  - **Consistency**: Date sequence validation (`created_at <= updated_at`), calculated age vs birth year consistency, city-to-state lookup coherence.
  - **Uniqueness**: Source customer ID uniqueness, national ID uniqueness.
  - **Timeliness**: Freshness lag within 365 days.
- **Reporting**: Automatically outputs interactive HTML scorecards with column hygiene statistics.

### 3. Match, Merge & Survivorship (Gold)
- **Candidate Blocking**: Synthesizes blocking keys combining the first 3 letters of cleaned entity names + 3 digits of postal codes, cutting comparisons from $O(N^2)$ to partitioned subsets.
- **Multi-Attribute Similarity**: Employs `RapidFuzz.fuzz.token_sort_ratio` on names and addresses combined with exact email and normalized phone matching.
- **Threshold Routing**:
  - `Score >= 0.90`: Automated merge into Golden Record clusters.
  - `0.70 <= Score < 0.90`: Enqueued into the `steward_queue` for human data steward verification.
  - `Score < 0.70`: Retained as distinct entities.
- **Survivorship & Provenance**: Consolidation logic selects winning attributes using `most_recent`, `longest_complete`, or `trusted_source` (Salesforce CRM > SAP ERP > Web Portal) while preserving complete field-level provenance in `source_lineage (JSON)`.
- **Ground Truth Evaluation**: Evaluates predicted clusters against the hidden `true_entity_id` to report precision, recall, and F1.

### 4. AI Stewardship Layer (GenAI Core)
- **Structured Pydantic Validation**: All LLM outputs are validated against strict Pydantic schemas (`StandardizeLocationOutput`, `RoleClassificationOutput`, `IssueExplanationOutput`, `IncidentRecommendationOutput`).
- **Confidence Guardrails**: Model confidence scores are inspected. Values with `confidence >= 0.90` are auto-applied with immutable records written to `audit_log` (`old_value, new_value, changed_by, model, prompt_version, ts`). Values with `confidence < 0.90` are routed to the human steward queue.
- **Cost & Latency Optimization**: Raw strings are deduplicated prior to API invocation and responses are cached in a local SQLite/disk cache (`data/llm_cache.db`), yielding an **88%+ cache hit rate**.
- **Offline / Hybrid Resilience**: Seamlessly operates with Azure OpenAI or OpenAI, while featuring a high-fidelity built-in deterministic reasoning engine for offline development and zero-cost CI/CD testing.

### 5. Intelligent Monitoring & RAG Incident Recommender
- **Dynamic Anomaly Detection**: Calculates a rolling 14-day mean and standard deviation for null rates and record throughput, triggering alerts when $|Z| \ge 3.0$.
- **Alert Deduplication**: Enforces a 6-hour suppression window to prevent alert fatigue.
- **RAG-Style Incident Resolution**: Uses TF-IDF cosine similarity to retrieve the top-3 most similar historical incidents, drafts remediation steps citing prior incident IDs, and auto-executes low-risk runbook actions (e.g., extractor retries).

### 6. Four-Page Streamlit Operational Dashboard
- **Data Quality Scorecard**: Executive gauge, dimension breakdown, top 10 failing rules, before vs after score improvement.
- **Steward Workbench**: Interactive review queue with one-click **Approve** and **Reject** buttons that immediately update database state.
- **Pipeline Health**: Ingestion run ledger, SLA tracking, latency, and heartbeat status.
- **AI Performance**: Model confidence distribution histograms, auto-apply vs triage pie charts, and complete audit trail table.

---

## 🚀 Quickstart Guide

### 1. Prerequisites & Environment Setup
Clone the repository and install dependencies:
```bash
git clone https://github.com/aham-golash/dq-steward-ai.git
cd dq-steward-ai

# Create virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Generate Synthetic Master Data (50,000 Records)
```bash
python data/generate_synthetic.py
```
*Outputs `CRM_Salesforce_extract.csv`, `ERP_SAP_extract.csv`, `Web_Portal_extract.json`, and `ground_truth_clusters.json` into `data/raw/`.*

### 3. Run End-to-End Pipeline
```bash
# Full execution
python -m src.main run-pipeline

# Or run with a fast interactive sample (e.g., 5,000 records)
python -m src.main run-pipeline --sample 5000
```

### 4. Launch Streamlit Analytics Dashboard
```bash
streamlit run dashboards/streamlit_app.py
```
Open **`http://localhost:8501`** in your browser.

### 5. Run Automated Tests with Coverage
```bash
python -m pytest tests/ --cov=src --cov-report=term-missing
```

---

## 🐳 Docker Deployment

Run the complete platform with PostgreSQL and Streamlit using Docker Compose:
```bash
docker-compose up --build
```
- Streamlit Dashboard: `http://localhost:8501`
- PostgreSQL Database: `localhost:5432` (`dq_steward_db`)

---

## 💼 Alignment with Job Description & Resume Talking Points

### Mapping to Target Skills
| JD Requirement | Project Implementation |
| :--- | :--- |
| **AI-Powered Solutions for MDM Operations** | Fuzzy entity match/merge, candidate blocking, golden record survivorship, and steward queue. |
| **GenAI / NLP for Data Quality & Stewardship** | Structured Pydantic standardization, role classification, issue explainer, and audit trail. |
| **Intelligent Monitoring & Alerting** | Static SLA thresholds + dynamic 14-day rolling Z-score anomaly detection and Webhook dispatcher. |
| **Automated Incident Resolution** | Runbook automation (rule-based) + RAG similarity retrieval citing past incident resolutions. |
| **Dashboards & Operational Analytics** | 4-page Streamlit application (Data Quality Scorecard, Steward Workbench, Pipeline Health, AI Observability). |
| **AI Test Automation (Opkey-style Discipline)**| Automated pytest suite, data reconciliation, Playwright UI tests, and AI output regression testing. |

### Interview Talking Points
1. **Deterministic Rules First, GenAI for Edge Cases**: We apply fast, deterministic regex and lookups first to keep cost and latency near zero. The LLM is invoked only for fuzzy, ambiguous free-text fields.
2. **Eliminating Hallucinations**: Enforced via Pydantic schema validation, confidence thresholds (`>= 0.90`), human-in-the-loop review for lower confidence, and immutable audit logs.
3. **High-Performance Matching**: Blocking keys drastically reduce comparisons from quadratic $O(N^2)$ pairs to partitioned blocks, enabling fast fuzzy scoring across 50,000+ records.
4. **Testing Non-Deterministic AI**: Evaluated using a fixed golden benchmark of labelled inputs with a strict `>= 85%` accuracy assertion gate in GitHub Actions CI.
