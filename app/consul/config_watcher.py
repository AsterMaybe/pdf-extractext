"""
Consul KV configuration watcher for monolitico.

Provides long-polling blocking queries on a KV prefix with hot-reload
via atomic config swap. Falls back to environment variables.
"""

import base64
import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import consul  # python-consul2
import requests

logger = logging.getLogger(__name__)


@dataclass
class ConfigWatcherConfig:
    """Configuration for the Consul config watcher."""
    consul_address: str = "consul:8500"
    consul_token: Optional[str] = None
    prefix: str = "config/monolitico/"  # Must end with /
    on_change: Optional[Callable[[Dict[str, str]], None]] = None

    def __post_init__(self):
        self.consul_address = os.getenv("CONSUL_HTTP_ADDR", self.consul_address)
        self.consul_token = os.getenv("CONSUL_HTTP_TOKEN", self.consul_token)
        if not self.prefix.endswith("/"):
            self.prefix += "/"


class ConfigWatcher:
    """
    Watches Consul KV prefix for configuration changes.
    
    Uses blocking queries (long-polling) for efficient real-time updates.
    Provides atomic config swap via threading.Lock.
    Falls back to environment variables when Consul is unavailable.
    """

    def __init__(self, config: ConfigWatcherConfig):
        self.config = config
        self._client = self._create_client()
        self._current_config: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._wait_index: int = 0

    def _create_client(self) -> consul.Consul:
        """Create Consul client."""
        # Parse address (host:port)
        if "://" in self.config.consul_address:
            # Remove scheme if present
            addr = self.config.consul_address.split("://")[1]
        else:
            addr = self.config.consul_address
        
        host, port_str = addr.rsplit(":", 1)
        port = int(port_str)
        
        return consul.Consul(
            host=host,
            port=port,
            token=self.config.consul_token,
            scheme="http"
        )

    def start(self) -> None:
        """Start the config watcher in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("[consul-config] Watcher already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True, name="consul-config-watcher")
        self._thread.start()
        
        # Do initial fetch
        self._fetch_and_update()
        logger.info("[consul-config] Config watcher started for prefix: %s", self.config.prefix)

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the config watcher."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        logger.info("[consul-config] Config watcher stopped for prefix: %s", self.config.prefix)

    def get_config(self) -> Dict[str, str]:
        """Get current configuration snapshot (thread-safe)."""
        with self._lock:
            return self._current_config.copy()

    def get_string(self, key: str, env_key: str, fallback: str = "") -> str:
        """Get string config: Consul KV -> env var -> fallback."""
        with self._lock:
            if key in self._current_config and self._current_config[key]:
                return self._current_config[key]
        if v := os.getenv(env_key):
            return v
        return fallback

    def get_int(self, key: str, env_key: str, fallback: int = 0) -> int:
        """Get int config: Consul KV -> env var -> fallback."""
        with self._lock:
            if key in self._current_config and self._current_config[key]:
                try:
                    return int(self._current_config[key])
                except ValueError:
                    pass
        if v := os.getenv(env_key):
            try:
                return int(v)
            except ValueError:
                pass
        return fallback

    def get_float(self, key: str, env_key: str, fallback: float = 0.0) -> float:
        """Get float config: Consul KV -> env var -> fallback."""
        with self._lock:
            if key in self._current_config and self._current_config[key]:
                try:
                    return float(self._current_config[key])
                except ValueError:
                    pass
        if v := os.getenv(env_key):
            try:
                return float(v)
            except ValueError:
                pass
        return fallback

    def get_bool(self, key: str, env_key: str, fallback: bool = False) -> bool:
        """Get bool config: Consul KV -> env var -> fallback."""
        with self._lock:
            if key in self._current_config and self._current_config[key]:
                return self._current_config[key].lower() in ("true", "1", "yes", "on")
        if v := os.getenv(env_key):
            return v.lower() in ("true", "1", "yes", "on")
        return fallback

    def _watch_loop(self) -> None:
        """Main watch loop using blocking queries."""
        session = requests.Session()
        if self.config.consul_token:
            session.headers.update({"X-Consul-Token": self.config.consul_token})

        base_url = f"http://{self.config.consul_address}/v1/kv/{self.config.prefix}"

        while not self._stop_event.is_set():
            try:
                params = {
                    "recurse": "true",
                    "wait": "300s",  # 5 minute long poll
                    "index": self._wait_index,
                }
                
                resp = session.get(base_url, params=params, timeout=310)
                
                if self._stop_event.is_set():
                    break
                    
                if resp.status_code == 200:
                    # Update wait index for next query
                    if "X-Consul-Index" in resp.headers:
                        self._wait_index = int(resp.headers["X-Consul-Index"])
                    
                    # Parse and update config
                    kvp = resp.json()
                    self._parse_and_update(kvp)
                    
                elif resp.status_code == 404:
                    # No keys at prefix - clear config
                    self._parse_and_update([])
                    
                else:
                    logger.warning("[consul-config] Unexpected status %d: %s", resp.status_code, resp.text)
                    time.sleep(5)
                    
            except requests.exceptions.Timeout:
                # Normal for long-poll timeout, continue
                continue
            except requests.exceptions.RequestException as e:
                logger.error("[consul-config] Watch error: %s", e)
                time.sleep(5)
            except Exception as e:
                logger.exception("[consul-config] Unexpected error in watch loop: %s", e)
                time.sleep(5)

    def _fetch_and_update(self) -> None:
        """Do initial non-blocking fetch."""
        try:
            session = requests.Session()
            if self.config.consul_token:
                session.headers.update({"X-Consul-Token": self.config.consul_token})
            
            base_url = f"http://{self.config.consul_address}/v1/kv/{self.config.prefix}"
            resp = session.get(base_url, params={"recurse": "true"}, timeout=10)
            
            if resp.status_code == 200:
                kvp = resp.json()
                if "X-Consul-Index" in resp.headers:
                    self._wait_index = int(resp.headers["X-Consul-Index"])
                self._parse_and_update(kvp)
            elif resp.status_code == 404:
                self._parse_and_update([])
        except Exception as e:
            logger.warning("[consul-config] Initial fetch failed: %s", e)

    def _parse_and_update(self, kvp: list) -> None:
        """Parse KV pairs and atomically update config."""
        config = {}
        for pair in kvp:
            if "Key" not in pair or "Value" not in pair:
                continue
            # Strip prefix
            key = pair["Key"]
            if not key.startswith(self.config.prefix):
                continue
            key = key[len(self.config.prefix):]
            if not key:
                continue
            # Decode value (base64 encoded in Consul)
            try:
                val = base64.b64decode(pair["Value"]).decode("utf-8")
            except Exception:
                val = ""
            config[key] = val

        with self._lock:
            self._current_config = config

        logger.info("[consul-config] Config updated (%d keys): %s", len(config), list(config.keys()))

        # Notify callback if set
        if self.config.on_change:
            try:
                self.config.on_change(config)
            except Exception as e:
                logger.error("[consul-config] on_change callback failed: %s", e)


@contextmanager
def config_watcher(config: ConfigWatcherConfig):
    """Context manager for ConfigWatcher lifecycle."""
    watcher = ConfigWatcher(config)
    watcher.start()
    try:
        yield watcher
    finally:
        watcher.stop()


def unmarshal_json_config(val: str, target_type: type) -> Any:
    """Parse JSON config value into a dataclass or dict."""
    return json.loads(val)


def marshal_json_config(obj: Any) -> str:
    """Marshal config object to JSON for Consul KV."""
    return json.dumps(obj)