#!/usr/bin/bash

# build development environment in venv/
python -m venv venv && source venv/bin/activate
pip install --editable .
