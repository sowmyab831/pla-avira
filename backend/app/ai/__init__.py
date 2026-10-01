"""Avira AI gateway.

One typed entry point for every model call:

    authenticate → authorize → consent/data policy → resolve model →
    capability check → reserve budget → invoke provider → validate →
    record usage → respond

`services.llm_client` remains a compatibility facade over this package.
"""
