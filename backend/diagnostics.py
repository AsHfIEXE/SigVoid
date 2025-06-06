from typing import Dict

diagnostics_data: Dict = {"free_heap": 0, "uptime": 0}

def update_diagnostics(data: Dict):
    diagnostics_data.update({
        "free_heap": data.get("free_heap", 0),
        "uptime": data.get("uptime", 0) / 1000.0  # Convert to seconds
    })
    return diagnostics_data