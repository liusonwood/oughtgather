#!/usr/bin/env python3
import json
import os
import sys
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.fetchers import _load_plugins
from src.fetchers.base import _registry

def generate_fetcher_schema():
    _load_plugins()
    schema = {}
    for type_name, cls in _registry.items():
        schema[type_name] = {
            "src_placeholder": getattr(cls, "src_placeholder", ""),
            "schema": getattr(cls, "config_schema", {})
        }
    return schema

def update_html_editor():
    schema = generate_fetcher_schema()
    schema_js = f"const FETCHERS_SCHEMA = {json.dumps(schema, ensure_ascii=False, indent=2)};"
    
    # We find the file from project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    editor_path = os.path.join(project_root, "config-editor.html")
    if not os.path.exists(editor_path):
        print(f"Error: {editor_path} not found.")
        return
        
    with open(editor_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    pattern = r"(// DYNAMIC_FETCHERS_DATA_START\n)(.*?)(\n\s*// DYNAMIC_FETCHERS_DATA_END)"
    new_content, count = re.subn(pattern, f"\\1    {schema_js}\\3", content, flags=re.DOTALL)
    
    if count == 0:
        print("Warning: DYNAMIC_FETCHERS_DATA comments not found in config-editor.html.")
        return
        
    with open(editor_path, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    print(f"Successfully updated config-editor.html with {len(schema)} fetchers: {list(schema.keys())}")

if __name__ == "__main__":
    update_html_editor()
