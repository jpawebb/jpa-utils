import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from latex_renderer.core import process_markdown, render_equation
from latex_renderer.cli import main


@pytest.fixture
def temp_dir():
    """Provides a temporary directory for file operations."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@patch("subprocess.run")
def test_render_equation_success(mock_run, temp_dir):
    """Test that render_equation returns True when all CLI tools succeed."""
    output_png = temp_dir / "output.png"

    mock_pdf_result = MagicMock()
    mock_pdf_result.returncode = 0

    mock_ppm_result = MagicMock()
    mock_ppm_result.returncode = 0

    mock_convert_result = MagicMock()
    mock_convert_result.returncode = 0

    mock_run.side_effect = [mock_pdf_result, mock_ppm_result, mock_convert_result]

    original_exists = Path.exists

    def mock_exists_side_effect(self):
        if self.name in ("eq.pdf", "output.png") or "page" in self.name:
            return True
        return original_exists(self)

    with (
        patch.object(
            Path, "exists", autospec=True, side_effect=mock_exists_side_effect
        ),
        patch.object(Path, "glob", return_value=[temp_dir / "page-1.png"]),
    ):

        success = render_equation(
            r"x^2 + y^2 = z^2", output_png, is_block=True, dpi=200
        )
        assert success is True


@patch("subprocess.run")
def test_render_equation_pdflatex_failure(mock_run, temp_dir):
    """Test that render_equation gracefully fails if pdflatex errors out."""
    output_png = temp_dir / "output.png"

    mock_pdf_result = MagicMock()
    mock_pdf_result.returncode = 1
    mock_pdf_result.stdout = "! LaTeX Error: Something went wrong."
    mock_run.return_value = mock_pdf_result

    success = render_equation(r"\invalidCommand", output_png, is_block=True)
    assert success is False


def test_process_markdown_parsing(temp_dir):
    """Test markdown processing handles blocks, inline expressions, and filters out short pieces."""
    sample_md_content = (
        "# Document Title\n\n"
        "$$\\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}$$\n\n"
        "Inline formula $E = mc^2$ and too short $x$."
    )

    input_md = temp_dir / "input.md"
    input_md.write_text(sample_md_content, encoding="utf-8")
    output_dir = temp_dir / "output_assets"

    with patch("latex_renderer.core.render_equation", return_value=True) as mock_render:
        process_markdown(input_md, output_dir, dpi=150)

        assert mock_render.call_count == 2
        assert output_dir.exists()

        expected_output_md = output_dir / "input_with_equations.md"
        assert expected_output_md.exists()

        output_content = expected_output_md.read_text(encoding="utf-8")
        assert "![equation_block_001.png](equation_block_001.png)" in output_content
        assert "![equation_inline_001.png](equation_inline_001.png)" in output_content


def test_process_markdown_failed_rendering_fallback(temp_dir):
    """Test fallback markdown formatting when external conversion tools report failures."""
    sample_md_content = "Broken formula $$\\broken_command$$."

    input_md = temp_dir / "input.md"
    input_md.write_text(sample_md_content, encoding="utf-8")
    output_dir = temp_dir / "output_assets"

    with patch("latex_renderer.core.render_equation", return_value=False):
        process_markdown(input_md, output_dir)

        output_content = (output_dir / "input_with_equations.md").read_text(
            encoding="utf-8"
        )
        assert "" in output_content


def test_cli_missing_arguments():
    """Test that the script exits when no file argument is passed."""
    with patch.object(sys, "argv", ["cli.py"]):
        with pytest.raises(SystemExit) as exit_info:
            main()
        assert exit_info.value.code == 1


@patch("latex_renderer.cli.process_markdown")
def test_cli_valid_arguments(mock_process, temp_dir):
    """Test standard CLI arguments pass correctly down into execution functions."""
    fake_file = temp_dir / "test.md"
    fake_file.touch()

    with patch.object(
        sys, "argv", ["cli.py", str(fake_file), str(temp_dir / "out"), "300"]
    ):
        main()
        mock_process.assert_called_once_with(fake_file, temp_dir / "out", dpi=300)
