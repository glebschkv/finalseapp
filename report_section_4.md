# 4 -- Maintenance, Ethics, and Future Work

## 4.1 -- System Architecture and Maintainability

OBD InsightBot follows a layered architecture that separates concerns across four tiers: the user interface (PyQt6 widgets), the service layer (authentication, AI engine, OBD parsing, voice, severity classification), the data access layer (SQLAlchemy ORM with SQLite), and the configuration layer (Pydantic-based settings with environment variable overrides). Each tier communicates only with its immediate neighbours, which means changes to one layer do not propagate unpredictably through the system.

Table 4.1 summarises the module structure and the purpose of each component.

| Module | Files | Purpose |
|---|---|---|
| `src/ui/` | `main_window.py`, `login_screen.py`, `chat_screen.py`, `styles.py` | Desktop GUI built with PyQt6. Login/registration, chat interface, sidebar, voice controls, and styling. |
| `src/services/` | `auth_service.py`, `chat_service.py`, `obd_parser.py`, `granite_client.py`, `rag_pipeline.py`, `severity_classifier.py`, `voice_service.py` | All business logic. Stateless where possible; each service is independently testable. |
| `src/models/` | `base.py`, `user.py`, `chat.py` | SQLAlchemy 2.0 declarative models. Three tables (users, chats, messages) with cascade-delete relationships. |
| `src/config/` | `settings.py`, `logging_config.py` | Centralised configuration via environment variables; rotating file and console logging. |
| `src/utils/` | `validators.py`, `helpers.py`, `health_check.py` | Input validation, sanitisation, rate limiting, and system health checks. |
| `src/prompts/` | `templates.py` | Formatted LLM prompt templates for different query types. |
| `tests/` | 7 test modules, `conftest.py`, `fixtures/` | 101 unit tests covering all service-layer modules. |

The service layer is the most critical tier for maintenance. Each service class has a single responsibility: `AuthService` handles registration, login, sessions, and rate limiting; `OBDParser` handles CSV ingestion and metric extraction; `AIEngine` manages the RAG pipeline; `SeverityClassifier` assigns traffic-light levels; and `VoiceService` wraps the speech-to-text and text-to-speech pipelines. Because these services are decoupled from the UI, they can be modified, extended, or replaced without touching the interface code.


## 4.2 -- Dependency Management

The application relies on 16 runtime dependencies and 4 development/testing dependencies. Table 4.2 lists the major dependencies, their minimum pinned versions, and the risk each introduces from a maintenance perspective.

| Dependency | Min Version | Risk Level | Maintenance Notes |
|---|---|---|---|
| PyQt6 | 6.5.0 | Medium | Qt major versions can introduce breaking API changes. Riverbank Computing releases bindings tied to specific Qt versions, so upgrading requires testing the full UI. |
| LangChain | 0.1.0 | High | LangChain has a rapid release cadence with frequent breaking changes to its API surface. Community integrations (`langchain-community`) are versioned separately. We recommend pinning to a tested minor version. |
| ChromaDB | 0.4.0 | Medium | ChromaDB's storage format has changed between minor versions. Upgrading may require re-indexing vector stores. |
| faster-whisper | 1.0.0 | Low | Stable wrapper around CTranslate2. Model weights are backward-compatible. |
| edge-tts | 7.0.0 | Medium | Depends on Microsoft Edge's undocumented TTS endpoint. If Microsoft changes or restricts the endpoint, this dependency would break without warning. |
| SQLAlchemy | 2.0.0 | Low | Mature ORM with strong backward compatibility guarantees within major versions. |
| bcrypt | 4.0.0 | Low | Stable cryptographic library. Hash format is forward-compatible by design. |
| Ollama | N/A (external) | Medium | Not a Python dependency but a required system service. Model naming conventions occasionally change between Ollama releases. |

To reduce dependency risk, we recommend that any future maintainer pin all dependencies to exact versions in a lock file (e.g. `pip freeze > requirements.lock`) and test upgrades in an isolated environment before deploying.


## 4.3 -- Testing and Quality Assurance

The project includes 101 automated tests across 7 test modules, executed via pytest. Table 4.3 breaks down coverage by module.

| Test Module | Tests | Scope |
|---|---|---|
| `test_auth.py` | 19 | Registration validation, login flow, session creation/expiry, rate limiting (5 attempts / 5 min for login, 3 / hour for registration), password hashing, account deletion with cascade |
| `test_obd_parser.py` | 15 | CSV column validation, metric extraction (RPM, coolant temp, speed, throttle, engine load), DTC detection and lookup, malformed file handling, edge cases (empty files, non-CSV input) |
| `test_severity.py` | 25 | Metric threshold analysis, DTC prefix-based severity, keyword detection in AI responses, negation-aware parsing (e.g. "no critical issues" classified as normal), combined multi-signal classification |
| `test_chat_service.py` | 13 | Chat CRUD, message storage and retrieval, title updates, chat history ordering, cascade deletion when user is removed |
| `test_ai_engine.py` | 13 | RAG prompt construction, context chunk retrieval, demo mode fallback, Ollama connection error handling (all external calls mocked) |
| `test_voice.py` | 8 | Model preloading, transcription pipeline, TTS generation, error handling for missing audio hardware (all external calls mocked) |
| `test_settings.py` | 8 | Default values, environment variable overrides, Ollama reachability validation, singleton pattern |

All tests use isolated temporary databases created via pytest fixtures, and rate limiters are automatically reset between tests using an `autouse` fixture. External dependencies (Ollama, faster-whisper, edge-tts) are mocked to ensure tests run without network access or specialised hardware.

No CI/CD pipeline is currently configured. Tests are run manually with:

    pytest tests/ -v --cov=src --cov-report=term-missing

We recommend that any future maintainer add a GitHub Actions workflow to run the test suite on every push and pull request. A minimal configuration would run `pytest` against Python 3.11 on Ubuntu, which matches the primary development environment.


## 4.4 -- Database Schema and Data Management

The application stores all persistent data in a single SQLite database file (`data/obd_insightbot.db`). The schema consists of three tables with foreign key relationships and cascade-delete behaviour.

| Table | Column | Type | Constraints |
|---|---|---|---|
| **users** | `id` | INTEGER | Primary key, auto-increment |
| | `username` | VARCHAR(50) | Unique, not null, indexed |
| | `password_hash` | VARCHAR(128) | Not null |
| | `created_at` | DATETIME | Default: UTC now |
| **chats** | `id` | INTEGER | Primary key, auto-increment |
| | `user_id` | INTEGER | Foreign key -> users.id, not null, indexed |
| | `title` | VARCHAR(100) | Default: "New Chat" |
| | `created_at` | DATETIME | Default: UTC now |
| | `updated_at` | DATETIME | Default: UTC now, auto-update |
| **messages** | `id` | INTEGER | Primary key, auto-increment |
| | `chat_id` | INTEGER | Foreign key -> chats.id, not null, indexed |
| | `role` | VARCHAR(20) | Not null ("user", "assistant", "system") |
| | `content` | TEXT | Not null |
| | `severity` | VARCHAR(20) | Nullable ("critical", "warning", "normal") |
| | `csv_file_path` | VARCHAR(500) | Nullable |
| | `timestamp` | DATETIME | Default: UTC now |

Deleting a user cascades to all their chats, which in turn cascades to all messages. This ensures no orphaned records remain after account deletion.

The SQLAlchemy engine is configured with connection pooling (`pool_size=5`, `max_overflow=10`) and `pool_pre_ping=True` to detect stale connections. While SQLite does not benefit from connection pooling in the same way a client-server database would, these settings prevent file-locking issues under concurrent access from multiple threads (e.g. the UI thread and voice processing thread).

For backup purposes, the entire application state can be preserved by copying the single `.db` file. No migration framework (such as Alembic) is currently in place. If the schema changes in a future release, we recommend adding Alembic to manage versioned migrations rather than relying on manual `ALTER TABLE` statements.


## 4.5 -- Security Considerations

Security was a design priority given that the application handles vehicle diagnostic data and user credentials. Table 4.5 summarises the security measures in place.

| Threat | Mitigation | Implementation Detail |
|---|---|---|
| Password compromise | bcrypt hashing | 12 rounds, per-password salt. Cost factor makes brute-force attacks computationally prohibitive [1]. |
| Session hijacking | Cryptographic tokens | 256-bit entropy via Python `secrets.token_urlsafe(32)`. Sessions expire after 24 hours. |
| Brute-force login | Rate limiting | 5 login attempts per 5 minutes; 3 registration attempts per hour. Configurable per-identifier window. |
| SQL injection | Parameterised queries | All database access through SQLAlchemy ORM. No raw SQL strings. |
| Input injection | Validation layer | Usernames restricted to alphanumeric + underscore (regex `^[a-zA-Z0-9_]+$`), 3--50 chars. Passwords minimum 6 chars. CSV files validated for correct headers before parsing. |
| Data exfiltration | Local-first architecture | All AI inference runs on the user's machine via Ollama. No OBD data, chat history, or credentials are transmitted to external servers. |
| Residual data after deletion | Cascade delete | Account deletion removes all associated chats and messages from the database in a single transaction. |

One area that warrants attention is the edge-tts dependency. While no user-generated data is sent to Microsoft's servers (only AI-generated response text is synthesised), the TTS request does leave the local machine. This is documented in the application's settings dialog, and a future release could offer a fully offline TTS alternative once local models reach comparable quality.

Password storage follows the recommendations of Provos and Mazieres [1], and the cost factor of 12 is consistent with OWASP's 2023 guidelines for bcrypt [2]. Session tokens use Python's `secrets` module, which draws from the operating system's cryptographically secure random number generator (`/dev/urandom` on Linux, `CryptGenRandom` on Windows).


## 4.6 -- Ethical Considerations

### 4.6.1 -- Data Privacy and User Autonomy

The local-first design was a deliberate ethical choice, not just a technical one. Vehicle diagnostic data can reveal sensitive information about a driver's habits, location patterns (through speed and RPM profiles), and vehicle condition. Sending this data to a cloud service would create a privacy risk that is disproportionate to the functionality gained. By running the language model, the vector store, and the database entirely on the user's machine, the application ensures that vehicle data never leaves the owner's control.

Users can delete their accounts at any time, and deletion is immediate and complete. There is no retention period, no "soft delete", and no data that persists after the operation. This aligns with the data minimisation principle described in the UK GDPR (Article 5(1)(c)) and gives users genuine control over their information.

### 4.6.2 -- AI Transparency and Limitations

The system uses RAG to ground its responses in the user's actual OBD-II data, which reduces but does not eliminate the risk of hallucination. We took three steps to manage this risk:

1. The system prompt explicitly instructs the language model to base its answers on the retrieved diagnostic data and to acknowledge when it does not have enough information to give a definitive answer.
2. Every AI response is passed through the SeverityClassifier, which uses rule-based logic (metric thresholds, DTC prefix matching, keyword analysis with negation detection) as an independent check on the model's output. If the classifier detects critical indicators that the model's response understates, the severity is elevated.
3. For any fault classified as critical or warning, the system recommends that the user consult a qualified mechanic. The application does not position itself as a replacement for professional diagnosis.

We recognise that a 2-billion parameter model has inherent limitations in technical reasoning compared to larger models. The decision to use Granite 3.3 2B was a trade-off between capability and the requirement for local execution on consumer hardware. Users should treat the chatbot's responses as a starting point for understanding their vehicle's condition, not as a definitive diagnosis.

### 4.6.3 -- Accessibility

Voice interaction was implemented primarily at the client's request to support hands-free use, but it also serves as an accessibility feature for users who find text-based interfaces difficult. The traffic-light severity system (red, amber, green) provides an at-a-glance indication of urgency that does not depend on reading or interpreting technical language. Future work could extend accessibility further by adding screen reader support via Qt's accessibility API and providing high-contrast or colour-blind-friendly theme options.

### 4.6.4 -- Environmental Impact

Running a language model locally consumes more energy per query than a shared cloud deployment, where inference hardware is optimised and amortised across many users. However, the Granite 3.3 2B model is small enough that its energy footprint on a modern CPU is modest -- comparable to running a video call. We considered this an acceptable trade-off given the privacy benefits of local inference.


## 4.7 -- Known Limitations

Table 4.7 lists the current limitations of the system and their impact.

| Limitation | Impact | Suggested Resolution |
|---|---|---|
| No database migration framework | Schema changes in future releases require manual intervention or data loss | Add Alembic for versioned schema migrations |
| No CI/CD pipeline | Tests must be run manually; regressions can reach the main branch undetected | Add GitHub Actions workflow for automated testing |
| No code linting or formatting enforcement | Code style may drift as new contributors join | Add ruff or flake8 configuration with a pre-commit hook |
| edge-tts requires internet | Voice responses will not work offline | Investigate local TTS alternatives (e.g. Piper, Coqui) as they mature |
| LangChain API instability | Upgrades may introduce breaking changes | Pin to a tested version and upgrade deliberately |
| Single-user SQLite | Database does not support concurrent multi-user access | Acceptable for a desktop application; would need PostgreSQL for a server deployment |
| 2B parameter model | Limited reasoning depth compared to larger models | Allow users to select larger models (7B, 13B) if their hardware supports it |
| No PDF export | Users cannot export chat history as PDF | Add PDF generation via `reportlab` or `weasyprint` |
| No cloud AI fallback in production | If Ollama is not running, only demo mode is available | Complete the IBM watsonx.ai cloud mode integration |


## 4.8 -- Future Work

Based on the limitations above and feedback from our client, we identify five priorities for future development:

1. **CI/CD and code quality.** Adding a GitHub Actions pipeline that runs `pytest`, checks code style with `ruff`, and reports coverage on every pull request would be the single highest-impact improvement for long-term maintainability. This could be implemented in under a day using GitHub's standard Python workflow template.

2. **Cloud mode completion.** The codebase includes a placeholder for IBM watsonx.ai integration, which would allow users with an API key to use larger, more capable models for complex diagnostic queries while still keeping data handling transparent. This would give users a choice between full local privacy and enhanced AI capability.

3. **Database migrations.** Introducing Alembic would allow future schema changes (such as adding a user preferences table or extending the message model with metadata) without requiring users to delete and recreate their database.

4. **Offline TTS.** Replacing edge-tts with a fully local text-to-speech solution would make the application entirely network-independent. The Piper TTS project is a strong candidate, as it supports ONNX-based inference and can run on CPU with acceptable latency, though voice quality does not yet match Microsoft's neural voices.

5. **Extended vehicle protocol support.** The current parser handles the generic OBD-II PID set defined in SAE J1979. Many modern vehicles expose manufacturer-specific extended PIDs (sometimes called "Mode 22" or "enhanced diagnostics") that provide richer data such as battery state-of-health for electric vehicles, transmission fluid temperature, or turbo boost pressure. Adding a plugin system for manufacturer-specific PID definitions would significantly expand the application's usefulness.


## References

[1] N. Provos and D. Mazieres, "A Future-Adaptable Password Scheme," in Proceedings of the USENIX Annual Technical Conference, FREENIX Track, 1999, pp. 81--91.

[2] OWASP Foundation, "Password Storage Cheat Sheet," OWASP Cheat Sheet Series, 2023. Available: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html

[3] UK Government, "Guide to the General Data Protection Regulation (UK GDPR)," Information Commissioner's Office, 2021. Available: https://ico.org.uk/for-organisations/guide-to-data-protection/guide-to-the-general-data-protection-regulation-gdpr/

[4] SAE International, "J1979-2: E/E Diagnostic Test Modes," SAE Standard, revised 2021.
