import sys
from pathlib import Path
from latex_renderer.core import process_markdown


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run -m latex_renderer.cli <input_md> [output_dir] [dpi]")
        sys.exit(1)

    input_md = Path(sys.argv[1])
    output_path = (
        Path(sys.argv[2]) if len(sys.argv) > 2 else input_md.parent / "equations_output"
    )
    dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 200

    if not input_md.is_file():
        print(f"Error: {input_md} is not a valid file.")
        sys.exit(1)

    process_markdown(input_md, output_path, dpi=dpi)


if __name__ == "__main__":
    main()
