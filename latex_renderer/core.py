import re
import shutil
import subprocess
import tempfile
from pathlib import Path

BLOCK_TEMPLATE = r"""\documentclass{{article}}
\usepackage{{amsmath,amssymb,amsfonts}}
\usepackage[paperwidth=20cm,paperheight=20cm,margin=0.3cm]{{geometry}}
\pagestyle{{empty}}
\begin{{document}}
\begin{{align*}}
{equation}
\end{{align*}}
\end{{document}}
"""

INLINE_TEMPLATE = r"""\documentclass{{article}}
\usepackage{{amsmath,amssymb,amsfonts}}
\usepackage[paperwidth=20cm,paperheight=5cm,margin=0.3cm]{{geometry}}
\pagestyle{{empty}}
\begin{{document}}
${equation}$
\end{{document}}
"""

BLOCK_RE = re.compile(r"\$\$(.*?\$\$)", re.DOTALL)
INLINE_RE = re.compile(r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)", re.DOTALL)

MIN_LENGTH = 3


def render_equation(
    latex: str, output_path: Path, is_block: bool = True, dpi: int = 200
) -> bool:
    """Renders a LaTeX snippet to a tightly cropped PNG.
    Returns a True on success, False with printed warning on failure.

    Args:
        latex (str): The LaTeX code equation to render.
        output_path (Path): The output destination of the file.
        is_block (bool, optional): Whether the equation is to be treated as a block, if false, inline. Defaults to True.
        dpi (int, optional): Resolution in dots per inch, of the output image. Defaults to 200.

    Returns:
        bool: True on success, False on failure.
    """
    template = BLOCK_TEMPLATE if is_block else INLINE_TEMPLATE
    latex_clean = latex.strip().replace("\r\n", "\n").replace("\r", "\n")
    tex_source = template.format(equation=latex_clean)

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_file = Path(tmpdir) / "eq.tex"
        tex_file.write_text(tex_source, encoding="utf-8")

        # Compile LaTeX to PDF
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "eq.tex"],
            cwd=tmpdir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not (Path(tmpdir) / "eq.pdf").exists():
            log = (
                (Path(tmpdir) / "eq.log").read_text(errors="replace")
                if (Path(tmpdir) / "eq.log").exists()
                else result.stdout
            )

            errors = [logl for logl in log.splitlines() if logl.startswith("!")]
            msg = " | ".join(errors[:3]) if errors else result.stdout[-200:]
            print(f"Warning: failed to render equation: {latex_clean[:30]}... | {msg}")
            return False

        # Convert PDF to PNG with pdftoppm
        ppm_prefix = Path(tmpdir) / "page"
        r = subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), "eq.pdf", str(ppm_prefix)],
            cwd=tmpdir,
            capture_output=True,
        )
        pngs = sorted(Path(tmpdir).glob("page*.png"))
        if not pngs:
            print(
                f"Warning: pdftoppm produced no output for equation: {latex_clean[:30]}..."
            )
            return False

        # Trim whitespace using ImageMagick's convert
        r = subprocess.run(
            [
                "convert",
                "-trim",
                "-bordercolor",
                "white",
                "-border",
                "10x6",
                str(pngs[0]),
                str(output_path),
            ],
            capture_output=True,
        )
        if r.returncode != 0 or not output_path.exists():
            shutil.copy(pngs[0], output_path)

    return True


def process_markdown(input_md: Path, output_dir: Path, dpi: int = 200):
    source = input_md.read_text(encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)

    replacements: list[tuple[str, str]] = []
    block_counter = 0
    inline_counter = 0
    ok_count = 0
    fail_count = 0

    # Block equations
    for match in BLOCK_RE.finditer(source):
        block_counter += 1
        latex = match.group(1)
        original = match.group(0)
        label = f"equation_block_{block_counter:03d}.png"
        png_path = output_dir / f"{label}.png"

        # Render and save
        ok = render_equation(latex, png_path, is_block=True, dpi=dpi)

        if ok:
            ok_count += 1
            replacement = f"\n\n![{label}]({label})\n\n"
        else:
            fail_count += 1
            replacement = f"\n\n<!-- RENDER FAILED -->\n```latex\n{original}\n```\n\n"

        replacements.append((original, replacement))

    # Inline equations
    for match in INLINE_RE.finditer(source):
        latex = match.group(1)
        original = match.group(0)

        if len(latex.strip()) < MIN_LENGTH:
            continue

        inline_counter += 1
        label = f"equation_inline_{inline_counter:03d}.png"
        png_path = output_dir / f"{label}.png"

        ok = render_equation(latex, png_path, is_block=False, dpi=dpi)

        if ok:
            ok_count += 1
            replacement = f"![{label}]({label})"
        else:
            fail_count += 1
            replacement = f"<!-- RENDER FAILED -->`{original}`"

        replacements.append((original, replacement))

    # Apply replacements
    replacements.sort(key=lambda x: len(x[0]), reverse=True)
    modified = source
    for original, replacement in replacements:
        modified = modified.replace(original, replacement, 1)

    # Write modified markdown
    out_md = output_dir / f"{input_md.stem}_with_equations.md"
    out_md.write_text(modified, encoding="utf-8")

    if fail_count:
        print(f"{fail_count} equations failed to render")
