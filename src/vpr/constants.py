"""Constants for the VPR module."""

import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = os.path.join(ROOT_DIR, 'data', 'vpr')
VARIANTS_JSON = os.path.join(DATA_DIR, 'variants.json')

BASE_URL = 'https://rus7-vpr.sdamgia.ru'
