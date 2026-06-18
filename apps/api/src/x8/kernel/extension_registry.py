from x8.kernel.capability_registry import CapabilityRegistration, CapabilityRegistry, default_registry


class ExtensionRegistry(CapabilityRegistry):
    pass


def default_extension_registry() -> ExtensionRegistry:
    registry = ExtensionRegistry()
    for capability in default_registry().all():
        registry.register(CapabilityRegistration(**capability.__dict__))
    return registry
