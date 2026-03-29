import sys
from pathlib import Path

# Add scripts/import to sys.path for test imports
scripts_import_path = Path(__file__).parent / "scripts" / "import"
sys.path.append(str(scripts_import_path))
