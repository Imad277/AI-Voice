"""PostgreSQL infrastructure: migration runner and organization-scoped transactions.

Uses the Phase 0 connection helpers and RLS conventions (``voiceos.tenancy``): the
application role is a non-owner without ``BYPASSRLS``; the tenant is bound
transaction-locally and only from trusted server-side objects.
"""
