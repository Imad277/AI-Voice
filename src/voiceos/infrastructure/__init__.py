"""Infrastructure layer (Phase 2): adapters that implement product ports.

Later home of PostgreSQL repositories, provider adapters, object storage, secret store and
external API clients. Adapters may import the domain, application ports, runtime contracts
and the Phase 0 core; nothing in the domain, application or runtime layers imports this
package. Empty until a concrete product PR needs an adapter (no speculative adapters).
"""
