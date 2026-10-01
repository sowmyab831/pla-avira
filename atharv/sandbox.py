import subprocess
import tempfile


def run_python_code(code):
    with tempfile.NamedTemporaryFile(
        suffix=".py",
        delete=False,
        mode="w"
    ) as f:

        f.write(code)

        file_name = f.name

    result = subprocess.run(
        ["python", file_name],
        capture_output=True,
        text=True,
        timeout=5
    )

    return {
        "stdout": result.stdout,
        "stderr": result.stderr
    }