"""JSON schema validation utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
import jsonschema
from rich.console import Console

console = Console()


def load_schema(schema_path: Path) -> dict[str, Any]:
    """Load a JSON schema from file."""
    with open(schema_path) as f:
        return json.load(f)


def validate_file(file_path: Path, schema: dict[str, Any]) -> list[str]:
    """Validate a JSON file against a schema.

    Returns:
        List of validation errors (empty if valid)
    """
    errors: list[str] = []

    try:
        with open(file_path) as f:
            data = json.load(f)

        jsonschema.validate(instance=data, schema=schema)

    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
    except jsonschema.ValidationError as e:
        errors.append(f"Schema validation error: {e.message}")
    except jsonschema.SchemaError as e:
        errors.append(f"Invalid schema: {e.message}")

    return errors


def validate_directory(
    directory: Path,
    schema: dict[str, Any],
    pattern: str = "*.json",
) -> dict[str, list[str]]:
    """Validate all JSON files in a directory.

    Returns:
        Dict mapping file paths to their validation errors
    """
    results: dict[str, list[str]] = {}

    for file_path in directory.glob(pattern):
        errors = validate_file(file_path, schema)
        if errors:
            results[str(file_path)] = errors

    return results


@click.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--schema",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Path to JSON schema",
)
def main(file_path: Path, schema: Path) -> None:
    """Validate a JSON file against a schema."""
    console.print(f"[bold blue]Validating {file_path}...[/bold blue]")

    schema_data = load_schema(schema)

    if file_path.is_dir():
        results = validate_directory(file_path, schema_data)
        if results:
            for path, errors in results.items():
                console.print(f"[red]✗ {path}[/red]")
                for error in errors:
                    console.print(f"    {error}")
            console.print(f"\n[red]{len(results)} file(s) failed validation[/red]")
        else:
            console.print("[green]✓ All files valid[/green]")
    else:
        errors = validate_file(file_path, schema_data)
        if errors:
            console.print(f"[red]✗ Validation failed[/red]")
            for error in errors:
                console.print(f"    {error}")
        else:
            console.print("[green]✓ Valid[/green]")


if __name__ == "__main__":
    main()
