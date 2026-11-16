#!/bin/bash
# Regenerates the statistics of the paper from the raw results in data/. Run from the repository root:  bash analysis/run_stats.sh
# Needs Python 3 with numpy and scipy.
#   1. analysis/stats6_regenerated.json  : laptop, desktop and the Linux VM (P = hardware threads visible to the container: 8, 16, 2),
#                                          with the two earlier laptop sessions (9 and 11 November) for the agreement check.
#                                          Compare with the shipped analysis/stats6.json (identical content).
#   2. analysis/stats3_regenerated.json  : the earlier sessions and the ECDSA power-state runs (11 November).
#                                          Compare with the shipped data/build/stats.json (identical content).
set -e
cd "$(dirname "$0")/.."
python3 -I analysis/stats_v4.py analysis/features3.jsonl analysis/configs.tsv analysis/stats6_regenerated.json \
  lap=data/res_lap:8 desk=data/res_desk:16 colab=data/res_colab:2 \
  old=nov9=data/zips/res9nov/results_20261109_003857/results.csv old=nov11=data/res_full/results_20261111_144909/results.csv
python3 -I analysis/stats_v3.py data analysis/stats3_regenerated.json
echo "written: analysis/stats6_regenerated.json analysis/stats3_regenerated.json"
