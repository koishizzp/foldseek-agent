#!/bin/bash

set -euo pipefail

QUERY=$1
DB=$2
OUT=$3

foldseek easy-search \
  "$QUERY" \
  "$DB" \
  "$OUT" \
  tmp \
  --format-output query,target,evalue,alntmscore,rmsd
