from typing import Any, Dict


class KVStorage:
    storage: Dict[str, Any] = {}

    def __init__(self, storage: Dict[str, Any] = None):
        if storage is not None:
            self.storage = storage
        else:
            self.storage = {}
    
    def set(self, key: str, value: Any) -> None:
        """Set a key-value pair in the storage."""
        self.storage[key] = value
        
    def get(self, key: str) -> Any:
        """Get the value associated with a key in the storage."""
        return self.storage.get(key, None)

    def delete(self, key: str) -> None:
        """Delete a key-value pair from the storage."""
        if key in self.storage:
            del self.storage[key]
        else:
            raise KeyError(f"Key '{key}' not found in storage.")
    
    def clear(self) -> None:
        """Clear all key-value pairs in the storage."""
        self.storage.clear()

    def update(self, key: str, value: Any) -> None:
        """Update the value associated with a key in the storage. but need to check the same type"""
        if key in self.storage:
            if isinstance(self.storage[key], type(value)):
                self.storage[key] = value
            else:
                raise TypeError(f"Type mismatch: Cannot update key '{key}' with value of type '{type(value).__name__}'. Expected type '{type(self.storage[key]).__name__}'.")
        else:
            raise KeyError(f"Key '{key}' not found in storage.")
    
        
