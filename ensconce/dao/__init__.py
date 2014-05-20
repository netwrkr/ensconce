"""
Package for DAO-like modules that get/set various values.

This is probably in need of further refactoring; this smells like an anti-pattern,
but it is how the code is currently organized.
"""
from collections import namedtuple

SearchResults = namedtuple('SearchResults', ['count', 'entries'])
