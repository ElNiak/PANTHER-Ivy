from plugins.services.implementations.protocol_interface import IProtocolPlugin
from plugins.services.testers.panther_ivy.service_manager import PantherIvyServiceManager

class PantherIvyPlugin(IProtocolPlugin):
    def __init__(self):
        self.service_managers = {}
    
    def get_service_manager(self, implementation_name: str):
        if implementation_name not in self.service_managers:
            # Dynamically import the service manager
            if implementation_name == "panther_ivy":
                from .service_manager import PantherIvyServiceManager
                self.service_managers[implementation_name] = PantherIvyServiceManager()
            else:
                raise ValueError(f"Unknown implementation '{implementation_name}' for QUIC protocol.")
        return self.service_managers[implementation_name]
