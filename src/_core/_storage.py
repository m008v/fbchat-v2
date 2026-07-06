from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod

class SessionStorage(ABC):
    """Abstract base class for session persistence."""
    
    @abstractmethod
    def load(self) -> str | None:
        """Load cookie string. Returns None if not found."""
        pass
    
    @abstractmethod
    def save(self, cookies: str) -> None:
        """Persist cookie string."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Delete stored session."""
        pass

class FileSessionStorage(SessionStorage):
    """JSON file backend for storing cookies."""
    
    def __init__(self, filepath: str = "config.json", key: str = "cookies"):
        self.filepath = filepath
        self.key = key
        
    def load(self) -> str | None:
        if not os.path.exists(self.filepath):
            return None
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(self.key)
        except (json.JSONDecodeError, OSError):
            return None
            
    def save(self, cookies: str) -> None:
        data = {}
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        
        data[self.key] = cookies
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
            
    def clear(self) -> None:
        if not os.path.exists(self.filepath):
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if self.key in data:
                del data[self.key]
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except (json.JSONDecodeError, OSError):
            pass

class EnvSessionStorage(SessionStorage):
    """Read/Write cookies from environment variable."""
    
    def __init__(self, env_var: str = "FB_COOKIES"):
        self.env_var = env_var
        
    def load(self) -> str | None:
        return os.environ.get(self.env_var)
            
    def save(self, cookies: str) -> None:
        # Saving to process env is mostly ephemeral, but keeps the interface
        os.environ[self.env_var] = cookies
        
    def clear(self) -> None:
        if self.env_var in os.environ:
            del os.environ[self.env_var]
