#!/usr/bin/env python3
"""Validate VERSION and create its annotated local Git release tag."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
VERSION_PATTERN = r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'


def git(*args):
    result = subprocess.run(
        ['git', '--no-optional-locks', '-C', str(ROOT), *args],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'Git command failed')
    return result.stdout.strip()


def version_tuple(value):
    match = re.fullmatch(VERSION_PATTERN, value)
    if not match:
        raise ValueError('VERSION must use MAJOR.MINOR.PATCH without leading zeros')
    return tuple(map(int, match.groups()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='validate without creating a tag')
    mode.add_argument('--check-tag', metavar='TAG', help='validate an existing release tag on HEAD (for CI)')
    args = parser.parse_args()
    try:
        if Path(git('rev-parse', '--show-toplevel')).resolve() != ROOT:
            raise ValueError('release.py must be in the Git repository root')
        if git('status', '--porcelain', '--untracked-files=all'):
            raise ValueError('Working tree must be clean; commit all release changes first')
        raw_version = (ROOT / 'VERSION').read_text(encoding='utf-8')
        version = raw_version.strip()
        current = version_tuple(version)
        if git('show', 'HEAD:VERSION') != raw_version.rstrip('\n'):
            raise ValueError('VERSION must be tracked and match the committed file at HEAD')
        target = 'v' + version
        tags = git('tag', '--list').splitlines()
        if args.check_tag:
            if args.check_tag not in (version, target):
                raise ValueError('Release tag must match VERSION: ' + target)
            if args.check_tag not in tags:
                raise ValueError('Release tag is not available locally; fetch tags before checking')
            if git('rev-parse', 'refs/tags/' + args.check_tag + '^{commit}') != git('rev-parse', 'HEAD'):
                raise ValueError('Release tag must point to HEAD')
        for tag in tags:
            match = re.fullmatch('v?(' + VERSION_PATTERN + ')', tag)
            if not match or tag == args.check_tag:
                continue
            if version_tuple(match.group(1)) >= current:
                raise ValueError(f'VERSION {version} must be greater than existing release {tag}')
        if args.check_tag:
            print('Validated release tag ' + args.check_tag)
        elif args.check:
            print('Ready to create ' + target)
        else:
            git('tag', '-a', target, '-m', 'Release ' + version)
            print(f'Created local annotated tag {target}. Nothing was pushed.')
    except (ValueError, OSError) as exc:
        print('Error: ' + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
