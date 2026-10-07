import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_SSH_TARGET = "root@192.168.20.43"


@dataclass(frozen=True, slots=True, kw_only=True)
class Settings:
    host: str
    port: int
    ssh_target: str
    ssh_timeout_seconds: float

    @classmethod
    def from_env(cls, *, environ: Mapping[str, str] = os.environ) -> "Settings":
        return cls(
            host=environ.get("HOMELAB_HOST", "127.0.0.1"),
            port=int(environ.get("PORT", "8765")),
            ssh_target=environ.get("HOMELAB_PVE_SSH_TARGET", DEFAULT_SSH_TARGET),
            ssh_timeout_seconds=float(environ.get("HOMELAB_SSH_TIMEOUT", "15")),
        )
