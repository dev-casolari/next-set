"""Create a source-only handoff, without secrets, caches or hosting identity."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / "dist/NextSet.zip"
target.parent.mkdir(exist_ok=True)
names = ["app", "tests", "scripts", "README.md", "TESTING.md", "pyproject.toml", "uv.lock", "Dockerfile", ".dockerignore", ".gitignore", ".env.example", "package.json"]
with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as archive:
    for name in names:
        path=ROOT/name
        files=path.rglob("*") if path.is_dir() else [path]
        for file in sorted(files):
            if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
                archive.write(file,Path("NextSet")/file.relative_to(ROOT))
print(f"Source archive: {target}")
