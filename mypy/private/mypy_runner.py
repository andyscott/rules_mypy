import argparse
import contextlib
import pathlib
import os
import shutil
import sys
import tempfile
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Iterator, List, Generator, Optional

import mypy.api
import mypy.util


def _merge_upstream_caches(cache_dir: str, upstream_caches: list[str]) -> None:
    current = pathlib.Path(cache_dir)
    current.mkdir(parents=True, exist_ok=True)

    for upstream_dir in upstream_caches:
        upstream = pathlib.Path(upstream_dir)

        # TODO(mark): maybe there's a more efficient way to synchronize the cache dirs?
        for dirpath_str, _, filenames in os.walk(upstream.as_posix()):
            dirpath = pathlib.Path(dirpath_str)
            relative_dir = dirpath.relative_to(upstream)
            for file in filenames:
                upstream_path = dirpath / file
                target_path = current / relative_dir / file
                if not target_path.parent.exists():
                    target_path.parent.mkdir(parents=True)
                if not target_path.exists():
                    shutil.copy(upstream_path, target_path)

    # missing_stubs is mutable, so remove it
    missing_stubs = current / "missing_stubs"
    if missing_stubs.exists():
        missing_stubs.unlink()


@contextlib.contextmanager
def managed_cache_dir(
    cache_dir: Optional[str], upstream_caches: list[str]
) -> Generator[str, Any, Any]:
    """
    Returns a managed cache directory.

    When cache_dir exists, returns a merged view of cache_dir with upstream_caches.
    Otherwise, returns a temporary directory that will be cleaned up when the resource
    is released.
    """
    if cache_dir:
        _merge_upstream_caches(cache_dir, list(upstream_caches))
        yield cache_dir
    else:
        tmpdir = tempfile.TemporaryDirectory()
        yield tmpdir.name
        tmpdir.cleanup()

@contextmanager
def symlink_tree(files: List[str]) -> Iterator[Path]:
    """
    Create a TemporaryDirectory containing a mirrored directory
    structure for each path in `files`, with symlinks pointing back
    to the originals. Yields the root Path of the tempdir.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        for file_path in files:
            src = Path(file_path).resolve()
            # Compute a “relative” path inside tmp:
            #  - if original was absolute, strip the anchor ('/' or 'C:\\', etc)
            #  - if relative, keep it as-is
            rel = src.relative_to(src.anchor) if src.is_absolute() else Path(file_path)
            dst = tmp_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(src, dst)
        yield tmp_root

def run_mypy(
    config_file: Optional[str], cache_dir: str, srcs: list[str]
) -> tuple[str, str, int]:
    maybe_config = ["--config-file", config_file] if config_file else []
    with symlink_tree(srcs) as root:
        report, errors, status = mypy.api.run(
            maybe_config
            + [
                # do not check mtime in cache
                "--skip-cache-mtime-checks",
                # mypy defaults to incremental, but force it on anyway
                "--incremental",
                # use a known cache-dir
                f"--cache-dir={cache_dir}",
                # use current dir + MYPYPATH to resolve deps
                "--explicit-package-bases",
                # speedup
                "--fast-module-lookup",
                # fatal error debugging
                "--show-traceback",
                str(root)
            ]
        )
        if status:
            sys.stderr.write(errors)
            sys.stderr.write(report)

        return report, errors, status


def run(
    output: Optional[str],
    cache_dir: Optional[str],
    upstream_caches: list[str],
    config_file: Optional[str],
    srcs: list[str],
) -> None:
    if len(srcs) > 0:
        with managed_cache_dir(cache_dir, upstream_caches) as cache_dir:
            report, errors, status = run_mypy(config_file, cache_dir, srcs)
    else:
        report, errors, status = "", "", 0

    if output:
        with open(output, "w+") as file:
            file.write(errors)
            file.write(report)

    # use mypy's hard_exit to exit without freeing objects, it can be meaningfully
    # faster than an orderly shutdown
    mypy.util.hard_exit(status)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=False)
    parser.add_argument("-c", "--cache-dir", required=False)
    parser.add_argument("--upstream-cache", required=False, action="append")
    parser.add_argument("--config-file", required=False)
    parser.add_argument("src", nargs="*")
    args = parser.parse_args()

    output: Optional[str] = args.output
    cache_dir: Optional[str] = args.cache_dir
    upstream_cache: list[str] = args.upstream_cache or []
    config_file: Optional[str] = args.config_file
    srcs: list[str] = args.src

    run(output, cache_dir, upstream_cache, config_file, srcs)


if __name__ == "__main__":
    main()
