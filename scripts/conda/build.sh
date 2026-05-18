#!/usr/bin/env bash

set -euxo pipefail

PACKAGE="holoviz_skills"

python -m build --sdist .

VERSION=$(python -c "import $PACKAGE; print($PACKAGE.__version__)")
export VERSION

conda build scripts/conda/recipe --no-anaconda-upload --no-verify -c conda-forge --package-format 2

mv "$CONDA_PREFIX/conda-bld/noarch/holoviz-skills-$VERSION-py_0.conda" dist
