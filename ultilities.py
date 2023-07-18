import sys
from os import path as op

clientId = "1118062711687872593"

def resourcePath(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = op.abspath(".")

    return op.join(base_path, relative_path)