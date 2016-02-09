#!/bin/bash
# Copyright (c) 2016 Jeremy W. Sherman, distributed under GPLv2+ WITHOUT ANY
# WARRANTY.
#
# Environment setup script for OS X Plover dev.

# Exit Statuses
EX_FAILURE_NO_CCTOOLS=1
EX_FAILURE_NO_32BIT_PYTHON=2
EX_FAILURE_NO_32BIT_WXPYTHON=3

PYTHON=${PYTHON:=$(which python)}
PIP=${PIP:=$(which pip)}

REAL_PYTHON=$("$PYTHON" -c 'import sys; print sys.executable')

echo "$0: using python: $PYTHON (executable: $REAL_PYTHON)"
echo "$0: using pip: $PIP (version: $($PIP --version))"


has_cli_tools() {
    echo "$0: checking for functioning cli tools by trying clang"
    if clang --version; then
      "true"
    else
      "false"
    fi
}


has_i386_python() {
    echo "$0: checking $REAL_PYTHON for 32-bit slice"
    if otool -vf "$REAL_PYTHON" | grep i386 >/dev/null; then
        "true"
    else
        "false"
    fi
}


has_i386_wx() {
    echo "$0: checking for working i386 wxPython"
    if arch -32 $REAL_PYTHON -c 'import wx' 2>&1 >/dev/null; then
        "true"
    else
        "false"
    fi
}


main() {
    if ! has_cli_tools; then
        cat 1>&2 <<EOT
CLI tools are not installed. Install Homebrew and do what it says. :)
Double-click the URL to visit: http://brew.sh/ for install instructions.
EOT
        exit $EX_FAILURE_NO_CCTOOLS
    else
        echo "$0: found clang, continuing"
    fi


    if ! has_i386_python; then
        cat 1>&2 <<EOT
$0: 32-bit Python is required, but
$PYTHON
doesn't have an i386 slice. Please run:

    brew uninstall python
    brew install python --universal --framework

or use a different Python by setting the PYTHON env var.
EOT
        exit $EX_FAILURE_NO_32BIT_PYTHON
    else
        echo "$0: 32-bit slice found"
    fi


    if ! has_i386_wx; then
        cat 1>&2 <<EOT
$0: 32-bit wxPython is required, but |import wx| when running
32-bit $PYTHON failed. Please run:

    brew uninstall wxpython
    brew install wxpython --universal
EOT
        exit $EX_FAILURE_NO_32BIT_WXPYTHON
    else
        echo "$0: successfully imported wx into 32-bit Python"
    fi


    echo "$0: installing required libraries using pip"
    pip install -r requirements.txt
}

main
