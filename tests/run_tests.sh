#!/bin/bash
source /home/ksj/BaroLaw/autorag_eval/venv/bin/activate
pip install requests > /dev/null 2>&1
cd /home/ksj/BaroLaw/tests
python3 test_runner.py
