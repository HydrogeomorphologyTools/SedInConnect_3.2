import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

@dataclass
class ProcessingParams:
    """Data class for processing parameters"""
    dtm_path: Path
    cell_size: float
    output_path: Path
    weight_path: Optional[Path] = None
    target_path: Optional[Path] = None
    sink_path: Optional[Path] = None
    use_cavalli_weight: bool = False
    normalize_weight: bool = False
    save_components: bool = False
    window_size: int = 5
    original_dtm_path: Optional[Path] = None
    roughness_path: Optional[Path] = None
    weight_output_path: Optional[Path] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        data = {}
        for key, value in asdict(self).items():
            if isinstance(value, Path):
                data[key] = str(value)
            else:
                data[key] = value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'ProcessingParams':
        """Create from dictionary"""
        path_fields = ['dtm_path', 'output_path', 'weight_path', 'target_path',
                       'sink_path', 'original_dtm_path', 'roughness_path', 'weight_output_path']
        for field in path_fields:
            if field in data and data[field] is not None and data[field] != '':
                data[field] = Path(data[field])
            elif field in data:
                data[field] = None
        return cls(**data)

    def save_to_file(self, filepath: Path):
        """Save parameters to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: Path) -> 'ProcessingParams':
        """Load parameters from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
