#!/bin/bash

rm -rf .env
python -m venv .env
source .env/bin/activate
pip install --upgrade pip

pip install \
  azure-functions \
  requests \
  lxml

pip freeze | grep -v "pkg_resources" > requirements.txt