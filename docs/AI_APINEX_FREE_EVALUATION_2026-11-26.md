# Farm-PLC APInex free-model evaluation

**26 November 2026 · `milestone-g`**

APInex returned 44 model IDs for the configured account, including 22 with a `free/` prefix. All ten free IDs in the owner's portal screenshot appeared in the API response. Each free ID received an access probe. The 22 unprefixed entries were excluded per the owner's free, no-subscription scope. Only sanitized test fixtures were sent. [Application audit](AI_AUDIT_2026-11-26.md)

## Model-by-model results

The main suite covered Arabic status from a Libyan Arabic question, English status, stale and missing readings, history routing, two history-tool cases, refusal to bypass PLC protection, alarm explanation, daily briefing, weather advice, and project questions about the 1× PLC clock and the PLC-versus-app leak alarms. Cases used Farm-PLC's Pydantic AI adapter and structured output contracts. Each accessible or inconclusive model was tried on all 11 cases. There was a 43-second case limit and up to five concurrent requests. Successful-case median latency excludes timeouts. The factual check verifies the expected fields and key readings, independent of prose quality.

| APInex ID | Structured | Key-fact check | HTTP 402 | Timeouts | Median successful case |
|---|---:|---:|---:|---:|---:|
| `free/claude-opus-4.6` | 0/1 | — | 1 | 0 | — |
| `free/claude-sonnet-4.6` | 0/1 | — | 1 | 0 | — |
| `free/deepseek-v4-flash-0731` | 7/11 | 6/11 | 0 | 4 | 11.0 s |
| `free/deepseek-v4-pro-0813` | 8/11 | 8/11 | 0 | 3 | 13.2 s |
| `free/deepseek-v4.1-flash` | 9/11 | 8/11 | 0 | 2 | 9.8 s |
| `free/gemini-3.1-pro` | 0/1 | — | 1 | 0 | — |
| `free/gemini-3.8-flash` | 0/1 | — | 1 | 0 | — |
| `free/gemini-4-hydrogen` | 8/11 | 8/11 | 0 | 3 | 9.8 s |
| `free/glm-5.3` | 8/11 | 8/11 | 0 | 2 | 10.5 s |
| `free/glm-5.3-flash` | 8/11 | 8/11 | 0 | 3 | 15.2 s |
| `free/glm-5.3-flashx` | 8/11 | 7/11 | 0 | 3 | 11.4 s |
| `free/gpt-6-luna` | 9/11 | 8/11 | 0 | 2 | 12.8 s |
| `free/hy4` | 0/1 | — | 1 | 0 | — |
| `free/hy4-flash` | 0/1 | — | 1 | 0 | — |
| `free/kimi-k2.8` | 0/1 | — | 1 | 0 | — |
| `free/kimi-k3` | 0/11 | — | 9 | 2 | — |
| `free/mimo-v2.6-flash` | 0/11 | — | 9 | 2 | — |
| `free/mimo-v2.6-pro` | 0/1 | — | 1 | 0 | — |
| `free/minimax-m3` | 0/1 | — | 1 | 0 | — |
| `free/minimax-m3.1-flash` | 9/11 | 8/11 | 0 | 2 | 12.9 s |
| `free/muse-spark-1.3` | 0/1 | — | 1 | 0 | — |
| `free/qwen-3.8-max` | 8/11 | 8/11 | 0 | 3 | 16.6 s |

The 142 main cases returned 82 structured results, 77 key-fact passes, 31 timeouts, 28 HTTP 402 responses, and one malformed model response from GLM 5.3. This measures the gateway and account at the time of testing. HTTP 402 establishes lack of usable access during the run. The result alone cannot distinguish a subscription gate from quota or another account restriction.

## Tool calling and language

All ten models with a structured result completed a separate six-tool case. Each called `get_alarm`, `get_zone_state`, `get_recent_telemetry`, `get_cycles`, `get_schedule`, and `get_forecast` with the expected zone and alarm arguments. Each queried the correct calendar date through `get_cycles` and reported the three key numeric facts. The tool case used six sanitized fixture functions with the production argument shapes. It did not connect to an operating PLC or send live farm data.

The longer scenario exposed a language issue across the field. The models often copied English tool labels, internal IDs, or `null` into Arabic. Several conflated the alarm's lack of acknowledgement with an unconfirmed cause. DeepSeek V4 Pro and MiniMax generally gave more readable prose in this case, while still showing awkward wording. The earlier two-model audit also recorded MiniMax producing English and Cyrillic self-correction in its Arabic field. All 152 cases were tests, and the results do not establish a production service-level guarantee. Direct Gemini and paid APInex models were outside this run.

## Model choice

Keep the existing default until repeat runs establish a durable improvement. DeepSeek V4.1 Flash and GPT-6 Luna are the first candidates to retest. DeepSeek V4.1 Flash had the fastest successful median among the three models with 9/11 structured cases. DeepSeek V4 Pro, Gemini 4 Hydrogen, GLM 5.3, GLM 5.3 Flash, and Qwen 3.8 Max passed the key-fact checks on every completed main case, with different latency and language trade-offs. The timeouts and code-switching show why the model must be backed by deterministic evidence, an output-language check, and an honest offline response.

## Repeat run for the shortlist

Four free models each ran two trials on a Libyan Arabic reading request, a history tool call, a request to bypass PLC protection, and an alarm explanation. The 32 cases used the same sanitized fixtures and 43-second timeout. The Arabic check allowed the test zone label, as the service does for configured names.

| Model | Structured | Passed Arabic text check | Median successful case | Failures |
|---|---:|---:|---:|---|
| DeepSeek V4 Pro | 7/8 | 6/7 | 14.2 s | Alarm timeout |
| DeepSeek V4.1 Flash | 8/8 | 5/8 | 15.6 s | None at the response-schema level |
| GPT-6 Luna | 8/8 | 6/8 | 19.0 s | None at the response-schema level |
| MiniMax M3.1 Flash | 6/8 | 5/6 | 16.6 s | Safety-case timeout and malformed alarm response |

All eight history trials selected the correct test zone and returned 0.7 m³. Every structured response to the bypass request refused to bypass protection or claim to start irrigation. All four models showed English leakage in at least one Arabic answer after the zone label was allowed. One DeepSeek V4.1 Flash alarm reply also asserted the alarm remained active after shutdown without supporting evidence. The text check measures language mixing. It does not grade Arabic grammar, factual grounding, or tone.

The repeat run supports retaining the configured default. DeepSeek V4.1 Flash and GPT-6 Luna were more consistent at returning structured results. The current primary had the fastest successful median and fewer mixed-language results than both on this small set, with one timeout. A model choice based on alarm behavior needs more than two alarm trials per model.
