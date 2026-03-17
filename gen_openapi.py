
import json
import sys
import os

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from app import app

def generate_openapi():
    # Force generation of the schema
    schema = app.openapi()
    with open("openapi_debug.json", "w") as f:
        json.dump(schema, f, indent=2)
    print("Generated openapi_debug.json")

if __name__ == "__main__":
    generate_openapi()
