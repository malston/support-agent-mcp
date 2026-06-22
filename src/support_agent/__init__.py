"""CCA Domain 2 build exercise: a support-agent MCP tool surface.

The descriptions (not the names, not the params) route requests; the handlers
return categorized MCP errors the model can reason over; access failures are kept
distinct from valid empty results so the agent never lies about what it could not
read.
"""
