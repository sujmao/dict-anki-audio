# -*- coding: utf-8 -*-
"""Minimal AnkiConnect client."""
import requests

AC = 'http://127.0.0.1:8765'


def ac(action, **params):
    r = requests.post(AC, json={'action': action, 'version': 6, 'params': params}, timeout=120)
    d = r.json()
    if d.get('error') is not None:
        raise RuntimeError('AnkiConnect %s: %s' % (action, d['error']))
    return d.get('result')
