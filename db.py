import csv
import threading
import atexit
from typing import Any, List, Dict, Optional
import duckdb


class CsvLogger:
    """
    A simple, efficient CSV logger leveraging Python's built-in buffering and DuckDB.

    Attributes:
        filename (str): CSV file path.
        fieldnames (List[str]): CSV column names.
        lock (threading.Lock): Ensures thread-safe writes.
        _file: File handle.
        _writer: csv.DictWriter instance.
    """

    def __init__(
        self, filename: str, fieldnames: List[str], buffer_size: int = 1_048_576
    ):
        """
        Initialize the CSV logger.

        :param filename: Path to the CSV file.
        :param fieldnames: List of column names.
        :param buffer_size: Buffer size in bytes (default 1MB).
        """
        self.filename = filename
        self.fieldnames = fieldnames
        self.lock = threading.Lock()
        # Open file with specified buffer size
        self._file = open(self.filename, "a", buffering=buffer_size, newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames)
        # Write header if file is new
        if self._file.tell() == 0:
            self._writer.writeheader()
        # Ensure file is closed on exit
        atexit.register(self.close)

    def log_event(self, event: Dict[str, Any]) -> None:
        """
        Log a single event to CSV.

        :param event: Dict mapping fieldnames to values.
        """
        try:
            with self.lock:
                self._writer.writerow(event)
        except Exception as e:
            # Basic error handling: print to stderr
            import sys

            print(f"[CsvLogger] Error writing event: {e}", file=sys.stderr)

    def flush(self) -> None:
        """Flush the I/O buffer to disk."""
        try:
            with self.lock:
                self._file.flush()
        except Exception as e:
            import sys

            print(f"[CsvLogger] Error flushing file: {e}", file=sys.stderr)

    def close(self) -> None:
        """Flush and close the file handle."""
        try:
            with self.lock:
                self._file.close()
        except Exception:
            pass

    @staticmethod
    def read_with_duckdb(filename: str, query: Optional[str] = None):
        """
        Read CSV data using DuckDB.

        :param filename: Path to CSV file.
        :param query: Optional SQL WHERE clause (without 'WHERE').
        :return: pandas.DataFrame
        """
        # Connect to an in-memory DuckDB instance
        con = duckdb.connect()
        if query:
            sql = f"SELECT * FROM read_csv_auto('{filename}') AS logs WHERE {query}"
        else:
            sql = f"SELECT * FROM read_csv_auto('{filename}') AS logs"
        # Return as pandas DataFrame
        return con.execute(sql).df()


if __name__ == "__main__":
    import time

    # Example usage
    logger = CsvLogger("events.csv", ["timestamp", "event_type", "value"])
    for i in range(5000):
        logger.log_event(
            {
                "timestamp": time.time(),
                "event_type": "tick",
                "value": {"v1": i, "v2": i * 2, "v3": i * 3},
            }
        )
    logger.flush()
    # Read back with DuckDB
    df = CsvLogger.read_with_duckdb("events.csv")
    print(df.head())
