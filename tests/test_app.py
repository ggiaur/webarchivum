import sys, os
sys.path.insert(0, os.path.abspath('.'))
import pytest
from src.app import *

def test_fő_funkciók_implementálása():
    assert fr_001_feature() == 'FR-001 OK'

