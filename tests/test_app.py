import sys, os
sys.path.insert(0, os.path.abspath('.'))
import pytest
from src.app import *

def test_autentikáció_és_biztonsági_javítások():
    assert fr_002_feature() == 'FR-002 OK'

