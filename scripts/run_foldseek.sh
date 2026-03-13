#!/bin/bash

set -euo pipefail

QUERY=$1
DB=$2
OUT=$3
TMP_DIR=${4:-tmp}

foldseek easy-search \
  "$QUERY" \
  "$DB" \
  "$OUT" \
  "$TMP_DIR" \
  --format-output query,target,evalue,alntmscore,rmsd,prob
