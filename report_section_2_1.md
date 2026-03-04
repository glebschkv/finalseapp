## 2.1 – Source Materials

The design and development of OBD InsightBot drew on a range of standards, research literature, and open-source tooling. This section identifies the key source materials that shaped the system's architecture and explains how each informed our approach.

### OBD-II Standards and Diagnostic Data

The project is grounded in the OBD-II diagnostic framework mandated for all passenger vehicles sold in the United States since 1996 and in the European Union since 2001 [1]. Two standards were particularly relevant. SAE J1979 [2] defines the diagnostic test modes and parameter identifiers (PIDs) used to request data from a vehicle's engine control unit, while ISO 15031-5 [3] specifies the format for emissions-related diagnostic services and the structure of diagnostic trouble codes (DTCs). Together, these standards provided the data model for our CSV parser: the metric types it expects (engine RPM, coolant temperature, throttle position, etc.), the five-character DTC format (e.g. P0300), and the distinction between generic and manufacturer-specific codes. Our fault code database of over 185 entries was compiled from the generic code definitions in ISO 15031-6 [4], cross-referenced against publicly available service manuals to assign severity levels and probable causes.

### Retrieval-Augmented Generation

The core AI capability of the system uses Retrieval-Augmented Generation (RAG), an approach first proposed by Lewis et al. [5] that combines a non-parametric retrieval step with a parametric language model. Rather than relying solely on the language model's pre-trained knowledge, RAG retrieves relevant documents at inference time and includes them as context in the prompt. This was a natural fit for our use case: the "documents" are the parsed OBD-II metrics and fault codes from a user's upload, and the language model draws on this vehicle-specific context when answering questions. The approach avoids fine-tuning and keeps the system general across any valid OBD-II log.

We implemented the RAG pipeline using LangChain [6], an open-source framework for building applications around large language models. LangChain provides abstractions for document loading, text splitting, embedding, vector storage, and prompt composition, which allowed us to assemble the retrieval pipeline without writing low-level integration code. Documents are chunked into 500-character segments with 50-character overlap and stored in ChromaDB [7], an open-source embedding database designed for similarity search over dense vectors. At query time, the most relevant chunks are retrieved and injected into a structured prompt before being sent to the language model.

### Language Model Selection

For the generative component of the pipeline, we selected IBM's Granite 3.3 2B parameter model [8]. Granite is a family of open-source large language models developed by IBM Research, trained on a curated mix of enterprise and technical data with a focus on transparency and responsible AI. The 2B variant was chosen because it balances capability against resource requirements: it runs comfortably on consumer hardware without a dedicated GPU, which was essential for meeting our local-first deployment goal. We considered larger models such as Llama 2 7B [9] and Mistral 7B [10], but both require substantially more RAM and are slower on CPU-only machines. Granite 3.3 2B produces coherent, contextually grounded answers at a fraction of the computational cost, and its open licence permits redistribution without restriction.

The model is served locally via Ollama [11], an open-source tool that packages language models as self-contained services accessible through a REST API. Ollama handles model downloading, quantisation, and inference, abstracting away the complexity of running a local LLM. This means no user data — including voice recordings, OBD logs, and chat history — leaves the user's machine, which was a firm requirement from our client. The privacy benefits of local inference are well documented in recent work on on-device language models [12], and several studies have argued that local-first architectures reduce the attack surface for sensitive data compared to cloud-based alternatives [13].

### Speech and Voice Interaction

Voice interaction was a client-requested feature to support hands-free use. For speech-to-text, we adopted faster-whisper [14], a CTranslate2-optimised reimplementation of OpenAI's Whisper model [15]. The original Whisper paper by Radford et al. demonstrated that a single encoder-decoder Transformer, trained on 680,000 hours of multilingual audio, can approach human-level transcription accuracy across a range of accents and noise conditions. The faster-whisper variant provides equivalent accuracy with significantly lower latency and memory usage, which was important for real-time dictation on consumer hardware. We use the "base" model size (74M parameters) to keep CPU inference under two seconds per utterance.

For text-to-speech we used edge-tts [16], a Python wrapper around Microsoft Edge's cloud-based neural TTS service. Microsoft's neural TTS system [17] uses a Transformer-based acoustic model to synthesise speech that is perceptually close to natural human speech. We chose the en-US-AriaNeural voice for clarity and naturalness. While edge-tts does require an internet connection, no user data is sent — only the AI-generated response text is synthesised. We evaluated local TTS alternatives such as Piper and Coqui, but both produced noticeably lower-quality output at the time of development.

### Desktop Application Framework

OBD InsightBot is a desktop application built with PyQt6 [18], the Python bindings for the Qt 6 application framework [19]. Qt is a mature, cross-platform toolkit that has been used in desktop software development for over 25 years, and it supports Windows, macOS, and Linux from a single codebase. We selected PyQt6 over alternatives such as Tkinter (limited widget set and dated appearance), Kivy (primarily targeted at mobile and touch interfaces), and Electron (large memory footprint and slower startup). PyQt6 provided native-looking widgets, a flexible layout system, and a well-documented signal-slot mechanism for event handling, all of which reduced development time and kept the application responsive.

### Data Storage and Security

User accounts, chat histories, and message logs are stored in SQLite [20], a self-contained, serverless relational database that requires no separate installation or administration. Gaffney et al. [21] note that SQLite is the most widely deployed database engine in the world, present in virtually every smartphone, web browser, and operating system, and its reliability and zero-configuration nature made it well suited to a locally-installed desktop application. We access SQLite through SQLAlchemy [22], a Python ORM that provides a declarative mapping between Python classes and database tables, reducing boilerplate and guarding against SQL injection through parameterised queries.

Password security follows the recommendations of Provos and Mazières [23], whose bcrypt algorithm is specifically designed to be computationally expensive in order to resist brute-force attacks. We hash passwords with bcrypt at a cost factor of 12 rounds, and session tokens are generated using Python's cryptographically secure `secrets` module with 256 bits of entropy. Rate limiting on login (5 attempts per 5 minutes) and registration (3 per hour) provides an additional layer of defence against automated attacks.

### Severity Classification

The traffic-light severity system (critical, warning, normal) applied to AI responses was informed by the risk classification approach common in automotive diagnostics. The SAE J2012 standard [24] defines a framework for categorising diagnostic trouble codes by urgency, and several commercial scan tools such as BlueDriver and FIXD use similar colour-coded schemes to communicate severity to non-expert users. Our SeverityClassifier combines three signals — metric threshold analysis, fault code prefix matching, and keyword-based response text analysis with negation detection — to produce a final severity level. The negation-aware approach was influenced by work on sentiment analysis in NLP [25], where detecting phrases like "no critical issues" is essential to avoid false positives.

### Summary

Table 2.1 summarises the key source materials and their role in the project.

| Source Material | Role in System |
|---|---|
| SAE J1979 / ISO 15031-5 / ISO 15031-6 | OBD-II data model, DTC format, fault code definitions |
| Lewis et al. (2020) — RAG | Core AI architecture for context-grounded responses |
| IBM Granite 3.3 2B | Local language model for generation |
| Ollama | Local model serving and inference |
| LangChain + ChromaDB | RAG pipeline orchestration and vector storage |
| Radford et al. (2023) — Whisper / faster-whisper | Speech-to-text transcription |
| Microsoft Neural TTS / edge-tts | Text-to-speech synthesis |
| PyQt6 / Qt 6 | Cross-platform desktop GUI |
| SQLite + SQLAlchemy | Local data storage and ORM |
| Provos & Mazières (1999) — bcrypt | Password hashing |
| SAE J2012 / commercial scan tools | Severity classification approach |

### References

[1] United States Environmental Protection Agency, "OBD II Regulations and Requirements," EPA-420-R-96-013, 1996.

[2] SAE International, "J1979-2: E/E Diagnostic Test Modes," SAE Standard, revised 2021.

[3] International Organization for Standardization, "ISO 15031-5: Road vehicles — Communication between vehicle and external equipment for emissions-related diagnostics — Part 5: Emissions-related diagnostic services," ISO, 2015.

[4] International Organization for Standardization, "ISO 15031-6: Road vehicles — Communication between vehicle and external equipment for emissions-related diagnostics — Part 6: Diagnostic trouble code definitions," ISO, 2015.

[5] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W. Yih, T. Rocktäschel, S. Riedel, and D. Kiela, "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," in Advances in Neural Information Processing Systems (NeurIPS), vol. 33, 2020, pp. 9459–9474.

[6] H. Chase, "LangChain: Building applications with LLMs through composability," GitHub repository, 2022. Available: https://github.com/langchain-ai/langchain

[7] J. Trein, A. Berber, and A. Asadullah, "Chroma: An open-source embedding database," GitHub repository, 2023. Available: https://github.com/chroma-core/chroma

[8] M. Abdelaziz, K. Drissi, et al., "Granite Code Models: A Family of Open Foundation Models for Code Intelligence," IBM Research, arXiv preprint arXiv:2405.04324, 2024.

[9] H. Touvron, L. Martin, K. Stone, et al., "Llama 2: Open Foundation and Fine-Tuned Chat Models," Meta AI, arXiv preprint arXiv:2307.09288, 2023.

[10] A. Jiang, A. Sablayrolles, A. Mensch, et al., "Mistral 7B," Mistral AI, arXiv preprint arXiv:2310.06825, 2023.

[11] Ollama, "Ollama: Get up and running with large language models locally," 2023. Available: https://ollama.com

[12] Y. Xu, S. Wang, P. Li, et al., "A Survey on Deploying Large Language Models on Edge Devices," IEEE Transactions on Artificial Intelligence, 2024.

[13] M. Kleppmann, A. Wiggins, P. van Hardenberg, and M. McGranaghan, "Local-First Software: You Own Your Data, in Spite of the Cloud," in ACM SIGPLAN International Symposium on New Ideas, New Paradigms, and Reflections on Programming and Software (Onward!), 2019, pp. 154–178. DOI: 10.1145/3359591.3359737

[14] SYSTRAN, "faster-whisper: Faster Whisper transcription with CTranslate2," GitHub repository, 2023. Available: https://github.com/SYSTRAN/faster-whisper

[15] A. Radford, J. W. Kim, T. Xu, G. Brockman, C. McLeavey, and I. Sutskever, "Robust Speech Recognition via Large-Scale Weak Supervision," in Proceedings of the 40th International Conference on Machine Learning (ICML), PMLR vol. 202, 2023, pp. 28492–28518.

[16] rany2, "edge-tts: Use Microsoft Edge's online text-to-speech service from Python," GitHub repository, 2023. Available: https://github.com/rany2/edge-tts

[17] Y. Ren, C. Hu, X. Tan, et al., "FastSpeech 2: Fast and High-Quality End-to-End Text to Speech," in Proceedings of the International Conference on Learning Representations (ICLR), 2021.

[18] Riverbank Computing, "PyQt6 Reference Guide," 2023. Available: https://www.riverbankcomputing.com/static/Docs/PyQt6/

[19] The Qt Company, "Qt 6 Documentation," 2023. Available: https://doc.qt.io/qt-6/

[20] D. R. Hipp, "SQLite," 2000. Available: https://sqlite.org

[21] K. P. Gaffney, M. Prammer, L. Brasfield, D. R. Hipp, D. Kennedy, and J. Patel, "SQLite: Past, Present, and Future," Proceedings of the VLDB Endowment, vol. 15, no. 12, pp. 3535–3547, 2022. DOI: 10.14778/3554821.3554842

[22] M. Bayer, "SQLAlchemy — The Database Toolkit for Python," 2006. Available: https://www.sqlalchemy.org

[23] N. Provos and D. Mazières, "A Future-Adaptable Password Scheme," in Proceedings of the USENIX Annual Technical Conference, FREENIX Track, 1999, pp. 81–91.

[24] SAE International, "J2012: Diagnostic Trouble Code Definitions," SAE Standard, revised 2020.

[25] C. J. Hutto and E. Gilbert, "VADER: A Parsimonious Rule-Based Model for Sentiment Analysis of Social Media Text," in Proceedings of the International AAAI Conference on Web and Social Media (ICWSM), vol. 8, no. 1, 2014, pp. 216–225.
