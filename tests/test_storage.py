import os
import json
import pytest
from _core._storage import FileSessionStorage, EnvSessionStorage

def test_file_session_storage(tmp_path):
    filepath = tmp_path / "config.json"
    storage = FileSessionStorage(filepath=str(filepath), key="cookies")
    
    # Test load when file doesn't exist
    assert storage.load() is None
    
    # Test save
    storage.save("c_user=123; xs=abc;")
    assert storage.load() == "c_user=123; xs=abc;"
    
    # Test clear
    storage.clear()
    assert storage.load() is None
    
    # Test save when file has other data
    with open(filepath, "w") as f:
        json.dump({"other_key": "value"}, f)
    storage.save("c_user=456; xs=def;")
    assert storage.load() == "c_user=456; xs=def;"
    
    with open(filepath, "r") as f:
        data = json.load(f)
    assert data["other_key"] == "value"
    assert data["cookies"] == "c_user=456; xs=def;"

def test_env_session_storage(monkeypatch):
    storage = EnvSessionStorage(env_var="TEST_FB_COOKIES")
    
    # Test load when env var doesn't exist
    monkeypatch.delenv("TEST_FB_COOKIES", raising=False)
    assert storage.load() is None
    
    # Test save
    storage.save("c_user=789; xs=ghi;")
    assert storage.load() == "c_user=789; xs=ghi;"
    assert os.environ["TEST_FB_COOKIES"] == "c_user=789; xs=ghi;"
    
    # Test clear
    storage.clear()
    assert storage.load() is None
    assert "TEST_FB_COOKIES" not in os.environ
