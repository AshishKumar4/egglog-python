#!/bin/bash
# Dew's egglog wheels, built from this branch's source as upstream's release builds them (.github/workflows/
# version.yml: maturin 1.15.0, the release's own generator, --release --locked, CPython 3.12, 3.13, 3.14 and 3.14t),
# for Linux TARGET at manylinux2014, with zig as the linker and libc (maturin --zig), as a host with no Docker builds
# the manylinux image's glibc floor, and the Rust toolchain rust-toolchain.toml pins. Everything it installs goes
# under a scratch directory of its own.
#
#   dew/build.sh TARGET OUT       TARGET x86_64 or aarch64; the wheels go to OUT
set -euo pipefail
target=$1
out=$(mkdir -p "$2" && cd "$2" && pwd)
here=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
export RUSTUP_HOME=$work/rustup CARGO_HOME=$work/cargo UV_PYTHON_INSTALL_DIR=$work/pythons
export PATH=$work/cargo/bin:$PATH
curl -fsSL https://sh.rustup.rs | sh -s -- -y -q --profile minimal --default-toolchain none --no-modify-path
toolchain=$(sed -n 's/^channel = "\(.*\)"/\1/p' "$here/rust-toolchain.toml")
rustup toolchain install "$toolchain" --profile minimal --target "$target-unknown-linux-gnu"
uv venv -q -p 3.12 "$work/tools"
uv pip install -q -p "$work/tools" maturin==1.15.0 ziglang==0.13.0.post1
# The interpreters it builds for, by name: an x86-64 build reads each one's own; an aarch64 one, maturin's bundled
# sysconfig of each.
uv python install 3.12 3.13 3.14 3.14t
# The tools' environment first, whose python3 runs zig (ziglang), which maturin finds there.
export PATH=$work/tools/bin:$(uv python dir --bin):$PATH
cd "$here"
"$work/tools/bin/maturin" build --release --locked --zig --target "$target-unknown-linux-gnu" \
  --compatibility manylinux2014 -o "$out" -i python3.12 python3.13 python3.14 python3.14t
ls "$out"
