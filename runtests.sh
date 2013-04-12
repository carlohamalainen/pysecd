#!/bin/bash

echo '42' | python -m doctest secd.py

python -m doctest compiler.py
