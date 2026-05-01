# Target Architecture

## Separation

- Website app (owner-operated)
- Product app (customer-operated per tenant)
- Control plane (internal ops automation)

## Local-first AI (Ollama)

The Ask C360 feature uses a local Ollama host process for NL→SQL generation and result summarization.

No direct provider-specific hardcoding in app logic.
