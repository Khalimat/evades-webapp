import csv
import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)

# Match ECO_ followed by exactly 7 digits
ECO_RE = re.compile(r'\b(ECO_\d{7})\b')

def load_eco_map():
    """
    Loads <yourapp>/data/eco_mapping.tsv (tab-separated) with columns:
    eco_label, definition, short

    Returns:
        dict: { 'ECO_0000005': {'short': '...', 'definition': '...'}, ... }
    """
    eco = {}
    app_root = Path(__file__).resolve().parent.parent
    path = app_root / 'data' / 'eco_mapping.tsv'

    if not path.exists():
        logger.error(f"[ECO] Mapping file not found: {path}")
        return eco

    try:
        with path.open(newline='', encoding='utf-8') as fh:
            reader = csv.DictReader(fh, delimiter='\t')
            for row in reader:
                code = row.get('eco_label')
                definition = row.get('definition')
                short = row.get('short') or ''
                if code and definition:
                    eco[code.strip()] = {
                        'short': short.strip(),
                        'definition': definition.strip()
                    }
                else:
                    logger.warning(f"[ECO] Skipping incomplete row: {row}")
    except Exception as e:
        logger.exception(f"[ECO] Failed to load mapping file {path}: {e}")
        return {}

    logger.info(f"[ECO] Loaded {len(eco)} ECO mappings from {path}")
    return eco