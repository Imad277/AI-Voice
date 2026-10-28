"""Product domain layer (Phase 2): business concepts, rules and value objects.

Innermost product layer. Modules here may import only ``voiceos.domain`` and the Phase 0
contracts in ``voiceos.core``. They never import application services, runtime contracts,
infrastructure adapters, database drivers, provider/runtime SDKs, test mocks or
``voiceos.benchmark`` (enforced by ``tests/unit/test_architecture.py``).
"""
