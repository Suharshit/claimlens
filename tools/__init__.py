"""ClaimLens tools: deterministic Python functions the agents call.

Rule: all money maths lives here, never in the LLM.
Every tool returns a Pydantic model or dict and calls ``append_log``.
"""
