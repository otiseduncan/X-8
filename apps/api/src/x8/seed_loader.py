from pathlib import Path


def main() -> None:
    root = Path("/app/knowledge")
    files = sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())
    print(f"XV8 seed loader found {len(files)} seed files.")


if __name__ == "__main__":
    main()
