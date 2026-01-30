#!/usr/bin/env python3
"""
Example: Complete Generated Application (Data Processor)

This demonstrates what mk14 now generates - full, functional code
instead of TODOs and placeholders.
"""

class DataProcessor:
    """Process and analyze data."""
    
    def __init__(self, data):
        """Initialize with data."""
        self.data = data
        self.results = {}
    
    def process(self):
        """Process the data completely."""
        if not self.data:
            return {"status": "empty", "count": 0}
        
        self.results = {
            "total_records": len(self.data),
            "keys": list(self.data[0].keys()) if self.data else [],
            "sample": self.data[0] if self.data else None,
            "statistics": self._compute_statistics()
        }
        return self.results
    
    def _compute_statistics(self):
        """Compute basic statistics."""
        if not self.data:
            return {}
        
        stats = {}
        for key in self.data[0].keys():
            values = [item.get(key) for item in self.data if isinstance(item.get(key), (int, float))]
            if values:
                stats[key] = {
                    "count": len(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values)
                }
        return stats
    
    def export(self, format_type="json"):
        """Export results in specified format."""
        import json
        if format_type == "json":
            return json.dumps(self.results, indent=2)
        return str(self.results)

def main_app():
    """Main application logic."""
    sample_data = [
        {"id": 1, "name": "Item A", "value": 100, "score": 8.5},
        {"id": 2, "name": "Item B", "value": 250, "score": 9.2},
        {"id": 3, "name": "Item C", "value": 150, "score": 7.8},
    ]
    
    processor = DataProcessor(sample_data)
    results = processor.process()
    
    print("=" * 60)
    print("Data Processing Results")
    print("=" * 60)
    print(processor.export())
    print("\nStatus: Complete ✓")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    import sys
    exit_code = main_app()
    sys.exit(exit_code if exit_code is not None else 0)
