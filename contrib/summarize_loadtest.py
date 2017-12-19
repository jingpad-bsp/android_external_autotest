#!/usr/bin/python

# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Load generator for devserver."""

import argparse
import ast
import itertools
import json
import operator
import pprint
import re
import sys

import common
from chromite.lib import commandline
from chromite.lib import cros_logging as logging


# Map ast to operator.
OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.USub: operator.neg,
    ast.Not: operator.not_,
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.Lt: operator.lt, ast.Gt: operator.gt,
    ast.LtE: operator.le, ast.GtE: operator.ge,
}

# Default keys to skip displaying.
DEFAULT_SKIP = [
    'build_name',
    'devserver',
    'name',
    'parent',
    'quick_provision',
    'trigger_response',
]

# List of commandline arguments for easy filtering.
FILTER_ARGS = [
    'board',
    'build_name',
    'devserver',
    'name',
    'status',
]


def get_parser():
  """Creates the argparse parser."""
  parser = commandline.ArgumentParser(description=__doc__)
  parser.add_argument('infile', nargs='*', type=argparse.FileType('r'),
                      help='Path to JSON file to read.',
                      default=[sys.stdin])
  parser.add_argument('--boards', type=str, action='store',
                      help='Boards to show.')
  parser.add_argument('--group', type=str, action='store',
                      help='Comma-spearated list of keys to group by.')
  parser.add_argument('--dump', action='store_true',
                      help='Dump all filtered entries.')
  parser.add_argument('--skip', type=str, action='store',
                      help='Comma-separated list of keys to skip displaying.',
                      default=','.join(DEFAULT_SKIP))
  parser.add_argument('--filter', type=str, action='store',
                      help='Filter expression to apply to each node.')
  for arg in FILTER_ARGS:
    parser.add_argument('--%s' % arg, type=str, action='store',
                        help='Comma-separated list of %s to filter by.' % arg)

  return parser

def eval_entry(expr, entry):
  """Perform evaluation of an expression.

  Named variables are interpreted as key-values from entry.
  """
  return eval_node(ast.parse(expr, mode='eval').body, entry)

def eval_node(node, entry):
  """Perform evaluation of a node."""
  if isinstance(node, ast.Num):
    return node.n
  elif isinstance(node, ast.Str):
    return node.s
  elif isinstance(node, ast.Name):
    if node.id == 'True':
      return True
    elif node.id == 'False':
      return False
    else:
      return entry[node.id]
  elif isinstance(node, ast.BinOp):
    return OPERATORS[type(node.op)](eval_node(node.left, entry),
                                    eval_node(node.right, entry))
  elif isinstance(node, ast.UnaryOp): # <operator> <operand> e.g., -1
    return OPERATORS[type(node.op)](eval_node(node.operand, entry))
  elif isinstance(node, ast.BoolOp): # <operator> <operand> e.g., -1
    if isinstance(node.op, ast.And):
      for value in node.values:
        if not eval_node(value, entry):
          return False
      return True
    elif isinstance(node.op, ast.Or):
      for value in node.values:
        if eval_node(value, entry):
          return True
      return False
    else:
      raise TypeError(node)
  elif isinstance(node, ast.Compare): # <operator> <operand> e.g., -1
    left = node.left
    for op, comparator in zip(node.ops, node.comparators):
      if not OPERATORS[type(op)](eval_node(left, entry),
                                 eval_node(comparator, entry)):
        return False
      left = comparator
    return True
  elif isinstance(node, ast.Call):
    if isinstance(node.func, ast.Name) and node.func.id == 'match':
      return re.match(eval_node(node.args[0], entry),
                      eval_node(node.args[1], entry))
    elif isinstance(node.func, ast.Name) and node.func.id == 'search':
      return re.search(eval_node(node.args[0], entry),
                       eval_node(node.args[1], entry))
    else:
      raise TypeError(node)
  else:
    raise TypeError(node)

def summarize_entries(entries, skip=set()):
  """Summarize a list of entries."""
  TAG_KEYS = [
      'board', 'build_name', 'devserver', 'name',
      'parent', 'quick_provision', 'status'
  ]
  VALUE_KEYS = [
      'avg_active', 'elapsed',
  ]
  summary = {
      'COUNT': len(entries),
  }
  summary.update({key: summarize_tags(entries, key) for key in TAG_KEYS
                  if key not in skip})
  summary.update({key: summarize_values(entries, key) for key in VALUE_KEYS
                  if key not in skip})
  return summary

def summarize_tags(entries, key):
  """Summarize all the different string values for a given key."""
  tags = {str(entry[key]) for entry in entries}
  return list(tags)

def summarize_values(entries, key):
  """Summarize the numeric values for a given key."""
  if entries is None or len(entries) == 0:
    return None

  values = [entry[key] for entry in entries if key in entry]
  summary = {}
  num_values = len(values)
  if num_values:
    summary['min'] = min(values)
    summary['max'] = max(values)
    summary['avg'] = sum(values) / num_values
  num_skipped = len(entries) - num_values
  if num_skipped:
    summary['num'] = num_values
    summary['skipped'] = num_skipped
  return summary

def group_entries(keys, entries):
  """Group entries based on different values of given keys.

  @param keys: A list of keys to group by.
  @param entries: A list of entries to split into groups.

  @return A list of list of entries, where each list has a different key value.
  """
  if not keys:
    return [entries]

  # Divide the group based on the first key.
  indexed = {}
  for entry in entries:
    value = str(entry[keys[0]])
    indexed.setdefault(value, []).append(entry)
  groups = [indexed[value] for value in sorted(indexed.keys())]

  # Recursively subdivide all the groups based on the rest of the keys.
  subgroups = []
  for group in groups:
    subgroups.extend(group_entries(keys[1:], group))
  return subgroups

def main(argv):
  """Load generator for a devserver."""
  parser = get_parser()
  options = parser.parse_args(argv)

  # Read entries from the specified file.
  all_entries = []
  for f in options.infile:
    all_entries.extend([json.loads(line) for line in f])

  # Filter entries:
  # - Ignore non-provisions.
  # - Filter via the specified FILTER_ARGS arguments.
  # - Filter via explicit filter request.
  entries = filter(lambda x: x['name'] != 'Runner', all_entries)
  for arg in FILTER_ARGS:
    if options.__dict__.get(arg):
      entries = filter(lambda x: x[arg] in options.__dict__[arg].split(','),
                       entries)
  if options.filter:
    entries = filter(lambda x: eval_entry(options.filter, x), entries)

  # Group the entries based on specified keys.
  groups = group_entries(options.group.split(',') if options.group else None,
                         entries)

  # Dump all filtered entries as groups, including their parents.
  if options.dump:
    dump_entries = itertools.chain(*groups)
    # Dump all entries, tracking needed parents.
    parents = []
    for entry in dump_entries:
      print(json.dumps(entry))
      if entry['parent'] not in parents:
        parents.append(entry['parent'])
    # Dump all parents.
    for entry in all_entries:
      if entry['id'] in parents:
        print(json.dumps(entry))

  # Summarize the entries, group by group.
  skip = options.skip.split(',') if options.skip else set()
  summaries = [summarize_entries(group, skip) for group in groups]
  print(json.dumps(summaries, indent=2))

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
