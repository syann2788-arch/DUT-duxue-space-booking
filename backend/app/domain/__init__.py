"""Domain service modules.

Routers import the module that owns a use case instead of depending on one
application-wide service file.  ``app.services`` remains a compatibility facade
for older integrations while new code uses these modules directly.
"""
