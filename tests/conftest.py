import os

# Ensure tests don't use real API keys
os.environ.setdefault("CONCIERGE_LLM_PROVIDER", "anthropic")
os.environ.setdefault("CONCIERGE_ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("CONCIERGE_SPACECADET_PATH", "")
