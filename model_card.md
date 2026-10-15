# DocuBot Model Card

## 1. System Overview

DocuBot answers developer questions using local project documentation. It compares naive generation, retrieval only, and retrieval augmented generation (RAG).

Inputs are a user question, Markdown or text files in docs/, and a Gemini API key for modes 1 and 3. Outputs are generated answers, retrieved sections labeled with filenames, or a refusal when evidence is insufficient.

## 2. Retrieval Design

Documents are loaded into memory. A tokenizer extracts lowercase alphanumeric words and removes common question words. An inverted index maps each remaining word to the filenames containing it.

Retrieval uses the index to find candidate files and splits their text at Markdown headings. Each section receives a score equal to the number of distinct query keywords it contains divided by the total number of distinct query keywords.

Sections scoring at least 0.3 are sorted highest first. The top three are returned by default. Ties retain their original order.

This design is simple and explainable, but exact keyword matching misses related word forms and synonyms. Section boundaries preserve examples and paragraphs, although some sections are longer than others. Several sections from one file can occupy every result slot.

## 3. Use of the LLM

- Mode 1 calls Gemini with the question alone. Despite labels describing full-document input, the actual naive method ignores all_text.
- Mode 2 returns retrieved text and filenames without calling Gemini.
- Mode 3 retrieves sections and sends them to Gemini. If retrieval returns nothing, DocuBot refuses without calling Gemini.

The RAG prompt requires answers to use only supplied snippets, avoid invented functions or endpoints, mention source files, and refuse when the snippets do not support an answer.

The configured model is gemini-flash-lite-latest. This alias may change over time.

## 4. Experiments and Comparisons

Identical questions were tested across all three modes. Full outputs are saved in comparison_results.txt.

| Query | Naive LLM | Retrieval only | RAG |
|---|---|---|---|
| Where is the auth token generated? | Asked for project context; did not guess. | Returned AUTH.md sections, including Token Generation. | Correctly named generate_access_token in auth_utils.py and cited AUTH.md. |
| How do I connect to the database? | Gave generic advice involving unsupported frameworks and JavaScript examples. | Returned SETUP.md sections with DATABASE_URL and initialization instructions. | Explained SQLite configuration and PostgreSQL initialization using SETUP.md. |
| Which endpoint lists all users? | Asked for context and suggested generic GET /users as an example. | Returned API_REFERENCE.md sections, including GET /api/users. | Correctly identified GET /api/users, but omitted its admin-only restriction. |
| How does a client refresh an access token? | Described a generic OAuth refresh-token flow with parameters not documented for this project. | Returned client workflow, POST /api/refresh, and validation sections. | Explained /api/refresh with an existing valid Bearer token and cited source files. |
| Which fields are stored in the users table? | Asked for schema context. | Refused despite the schema being present in DATABASE.md. | Also refused because retrieval returned no snippets. |
| Is there any mention of payment processing in these docs? | Asked to see the documentation. | Refused because no matching evidence was retrieved. | Refused without calling Gemini. |

Naive generation sometimes requested context appropriately, but other answers sounded detailed without being grounded in this project. Retrieval supplied inspectable evidence but required reading multiple sections. RAG made the evidence easier to understand, while inheriting retrieval failures.

The final retrieval evaluation reported 0.62, or 5 hits out of 8 queries. This measures expected-source retrieval, not answer accuracy. The payment question has no expected source and is counted as a miss even when the system appropriately refuses. The database query also counts as a miss despite retrieving relevant setup information. These limitations make manual review necessary.

## 5. Failure Cases and Guardrails

### Failure 1: Unsupported naive refresh instructions

For "How does a client refresh an access token?", naive mode described /oauth/token and refresh_token grant parameters. These were unsupported by the project docs. A project-specific answer should use the documented /api/refresh endpoint and acknowledge any conflicting instructions.

### Failure 2: False refusal for a documented schema

For "Which fields are stored in the users table?", retrieval and RAG both refused. DATABASE.md contains user_id, email, password_hash, and joined_at. The keyword threshold rejected the relevant section. Retrieval should surface the schema so RAG can answer from it.

### Failure 3: Missing access restriction

For "Which endpoint lists all users?", RAG identified GET /api/users but omitted the admin-only restriction present in its evidence. A more complete answer should include that restriction.

The docs also contain a refresh inconsistency: AUTH.md says to refresh when a token expires, while API_REFERENCE.md requires an existing valid token. The observed RAG answer followed the valid-token requirement without identifying the conflict.

The implemented guardrails are:
- Remove common words before scoring.
- Require a section score of at least 0.3.
- Limit results to the requested top_k.
- Refuse when retrieval returns no snippets.
- Instruct Gemini to use only retrieved evidence and cite files.

DocuBot should refuse for unrelated questions such as cake recipes, and for undocumented topics such as payment processing. A failed retrieval does not prove the answer is absent from the entire corpus.

## 6. Limitations and Future Improvements

Current limitations:
1. Exact keyword matching misses synonyms and word forms such as table versus Tables.
2. Ties and multiple results from one file can crowd out better evidence.
3. The threshold can reject answerable questions or accept weak matches.
4. Prompt instructions do not guarantee complete or correct answers.
5. Conflicting documentation can produce ambiguous guidance.

Future improvements:
1. Normalize word forms and compare keyword retrieval with semantic retrieval.
2. Tune scoring and thresholds using more answerable and unanswerable questions, and improve tie handling.
3. Evaluate snippet relevance, refusal quality, answer completeness, and source conflicts separately.

## 7. Responsible Use

Unsupported authentication or database instructions could lead developers to implement incorrect behavior or waste time debugging. Missing access restrictions could mislead users about endpoint permissions.

- Check cited source sections before acting on an answer.
- Verify important claims against actual code; these sample documents describe a fictional application.
- Treat refusals as a reason to inspect the docs or rephrase the question.
- Keep API keys private and excluded from Git.
