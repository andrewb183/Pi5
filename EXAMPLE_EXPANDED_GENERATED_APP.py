#!/usr/bin/env python3
"""Auto-generated application with full functionality."""

import sys
import json
from pathlib import Path
from typing import Any, Dict, List


class Logger:
    """Logging utility for tracking operations."""
    
    def __init__(self):
        """Initialize logger."""
        self.logs = []
    
    def log(self, level: str, message: str) -> None:
        """Log a message."""
        entry = {"level": level, "message": message, "timestamp": str(Path.cwd())}
        self.logs.append(entry)
    
    def get_logs(self) -> List[Dict]:
        """Get all logs."""
        return self.logs

class DataValidator:
    """Validate data structure and types."""
    
    def __init__(self, data: List[Dict]):
        """Initialize validator."""
        self.data = data
        self.errors = []
    
    def validate(self) -> bool:
        """Validate data structure."""
        if not isinstance(self.data, list):
            self.errors.append("Data must be a list")
            return False
        
        if len(self.data) == 0:
            self.errors.append("Data is empty")
            return False
        
        for i, item in enumerate(self.data):
            if not isinstance(item, dict):
                self.errors.append(f"Item {i} is not a dictionary")
        
        return len(self.errors) == 0
    
    def get_errors(self) -> List[str]:
        """Get validation errors."""
        return self.errors

class StatisticalAnalyzer:
    """Perform statistical analysis on numeric data."""
    
    def __init__(self, data: List[Dict]):
        """Initialize analyzer."""
        self.data = data
    
    def compute_statistics(self) -> Dict[str, Dict[str, float]]:
        """Compute comprehensive statistics."""
        if not self.data:
            return {}
        
        stats = {}
        keys = self.data[0].keys()
        
        for key in keys:
            values = [item.get(key) for item in self.data if isinstance(item.get(key), (int, float))]
            if values:
                stats[key] = self._calc_key_stats(values)
        
        return stats
    
    def _calc_key_stats(self, values: List[float]) -> Dict[str, float]:
        """Calculate statistics for a single key."""
        sorted_vals = sorted(values)
        n = len(values)
        
        return {
            "count": n,
            "sum": sum(values),
            "mean": sum(values) / n,
            "median": sorted_vals[n // 2],
            "min": min(values),
            "max": max(values),
            "range": max(values) - min(values)
        }

class DataFilter:
    """Filter data based on conditions."""
    
    def __init__(self, data: List[Dict]):
        """Initialize filter."""
        self.data = data
    
    def filter_by_key_value(self, key: str, value: Any) -> List[Dict]:
        """Filter data by key-value pair."""
        return [item for item in self.data if item.get(key) == value]
    
    def filter_by_range(self, key: str, min_val: float, max_val: float) -> List[Dict]:
        """Filter numeric data by range."""
        return [item for item in self.data 
                if min_val <= item.get(key, 0) <= max_val]

class DataSorter:
    """Sort data by various criteria."""
    
    def __init__(self, data: List[Dict]):
        """Initialize sorter."""
        self.data = data
    
    def sort_by_key(self, key: str, reverse: bool = False) -> List[Dict]:
        """Sort by a specific key."""
        return sorted(self.data, key=lambda x: x.get(key, 0), reverse=reverse)
    
    def sort_by_multiple_keys(self, keys: List[str]) -> List[Dict]:
        """Sort by multiple keys."""
        for key in reversed(keys):
            self.data = sorted(self.data, key=lambda x: x.get(key, 0))
        return self.data

class DataAggregator:
    """Aggregate data into summaries."""
    
    def __init__(self, data: List[Dict]):
        """Initialize aggregator."""
        self.data = data
    
    def group_by(self, key: str) -> Dict[str, List[Dict]]:
        """Group data by a key."""
        groups = {}
        for item in self.data:
            group_key = item.get(key)
            if group_key not in groups:
                groups[group_key] = []
            groups[group_key].append(item)
        return groups
    
    def aggregate_numeric(self, group_key: str, numeric_key: str) -> Dict:
        """Aggregate numeric values by group."""
        groups = self.group_by(group_key)
        aggregated = {}
        
        for group, items in groups.items():
            values = [item.get(numeric_key) for item in items if isinstance(item.get(numeric_key), (int, float))]
            if values:
                aggregated[group] = {
                    "count": len(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values)
                }
        
        return aggregated

class DataExporter:
    """Export data in various formats."""
    
    def __init__(self, data: List[Dict]):
        """Initialize exporter."""
        self.data = data
    
    def to_json(self) -> str:
        """Export as JSON."""
        return json.dumps(self.data, indent=2)
    
    def to_csv_string(self) -> str:
        """Export as CSV string."""
        if not self.data:
            return ""
        
        keys = list(self.data[0].keys())
        lines = [",".join(keys)]
        
        for item in self.data:
            values = [str(item.get(k, "")) for k in keys]
            lines.append(",".join(values))
        
        return "\n".join(lines)

class DataProcessor:
    """Main processor coordinating all operations."""
    
    def __init__(self, data: List[Dict]):
        """Initialize processor."""
        self.data = data
        self.logger = Logger()
        self.validator = DataValidator(data)
        self.analyzer = StatisticalAnalyzer(data)
        self.filter = DataFilter(data)
        self.sorter = DataSorter(data.copy() if data else [])
        self.aggregator = DataAggregator(data)
        self.exporter = DataExporter(data)
        self.results = {}
    
    def process_complete(self) -> Dict[str, Any]:
        """Run complete data processing pipeline."""
        self.logger.log("INFO", "Starting data processing")
        
        if not self.validator.validate():
            self.logger.log("ERROR", f"Validation failed: {self.validator.get_errors()}")
            return {"status": "validation_failed", "errors": self.validator.get_errors()}
        
        self.logger.log("INFO", "Data validation passed")
        
        self.results = {
            "total_records": len(self.data),
            "fields": list(self.data[0].keys()) if self.data else [],
            "statistics": self.analyzer.compute_statistics(),
            "sample_record": self.data[0] if self.data else None
        }
        
        self.logger.log("INFO", "Data processing completed")
        return {"status": "success", "results": self.results}
    
    def export(self, format_type: str = "json") -> str:
        """Export processed data."""
        if format_type == "csv":
            return self.exporter.to_csv_string()
        return self.exporter.to_json()

def main_app():
    """Main application logic."""
    sample_data = [
        {"id": 1, "category": "A", "name": "Item 1", "value": 100, "score": 8.5},
        {"id": 2, "category": "B", "name": "Item 2", "value": 250, "score": 9.2},
        {"id": 3, "category": "A", "name": "Item 3", "value": 150, "score": 7.8},
        {"id": 4, "category": "B", "name": "Item 4", "value": 200, "score": 8.9},
    ]
    
    processor = DataProcessor(sample_data)
    result = processor.process_complete()
    
    print("=" * 70)
    print("COMPREHENSIVE DATA PROCESSING APPLICATION")
    print("=" * 70)
    
    if result["status"] == "success":
        results = result["results"]
        print(f"\nTotal Records: {results['total_records']}")
        print(f"Fields: {results['fields']}")
        
        print("\nStatistics:")
        print(json.dumps(results["statistics"], indent=2))
        
        print("\nFiltered Data (value > 120):")
        filtered = processor.filter.filter_by_range("value", 120, 500)
        for item in filtered:
            print(f"  - {item}")
        
        print("\nAggregated by Category:")
        agg = processor.aggregator.aggregate_numeric("category", "value")
        print(json.dumps(agg, indent=2))
        
        print("\nSorted by Score (descending):")
        sorted_data = processor.sorter.sort_by_key("score", reverse=True)
        for item in sorted_data[:2]:
            print(f"  - {item}")
    
    print("\nStatus: Data processing complete ✓")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    exit_code = main_app()
    sys.exit(exit_code if exit_code is not None else 0)

