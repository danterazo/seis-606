import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

DEFAULT_SSH_HOST: Final[str] = "192.168.20.43"
DEFAULT_SSH_USER: Final[str] = "root"


@dataclass(frozen=True, slots=True, kw_only=True)
class Settings:
    host: str
    port: int
    ssh_host: str
    ssh_user: str
    ssh_timeout_seconds: float
    cache_seconds: float
    @classmethod
    def from_env(cls, *, environ: Mapping[str, str] = os.environ) -> "Settings":
        return cls(
            host=environ.get("HOMELAB_HOST", "127.0.0.1"),
            port=int(environ.get("PORT", "8765")),
            ssh_host=environ.get("HOMELAB_PVE_SSH_HOST", DEFAULT_SSH_HOST),
            ssh_user=environ.get("HOMELAB_PVE_SSH_USER", DEFAULT_SSH_USER),
            ssh_timeout_seconds=float(environ.get("HOMELAB_SSH_TIMEOUT", "15")),
            cache_seconds=float(environ.get("HOMELAB_CACHE_SECONDS", "10")),
        )
