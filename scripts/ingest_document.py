"""Index an authorized local document without transmitting it externally."""

import argparse
from pathlib import Path

from app.rag.api import extract, get_store

parser = argparse.ArgumentParser()
parser.add_argument("path", type=Path)
parser.add_argument("--title", required=True)
parser.add_argument("--source", required=True)
parser.add_argument("--authorized", action="store_true", required=True)
args = parser.parse_args()
pages = extract(args.path.name, args.path.read_bytes())
result = get_store().add(args.title, args.source, pages)
print(
    f"Indexed: {result['title']} ({result['chunks']} chunks; duplicate={result['duplicate']})"
)
