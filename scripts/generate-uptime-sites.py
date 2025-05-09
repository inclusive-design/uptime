#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pyyaml",
# ]
# ///

import argparse
import os
import re
import sys
import yaml
from pathlib import Path
from typing import List


def is_ignored(url: str, cfg: dict) -> bool:
    if any(pattern in url for pattern in cfg['ignore-records']):
        print(f"Ignoring {url} ...")
        return True
    return False


def process_url(url: str, cfg: dict) -> str:
    for substitution in cfg.get('url-substitutions', []):
        if substitution['name'] == url:
            url = substitution['url']
    # Remove any potential http protocol info here since https:// is specified
    # when writing hurl files
    url = re.sub(r'^https?://', '', url)
    if is_ignored(url=url, cfg=cfg):
        return ''
    return url


def process_record(apex_domain: str, subdomain: str, cfg: dict, upptimerc_path: str) -> None:
    record = f"{subdomain}.{apex_domain}" if subdomain else apex_domain
    url = process_url(url=record, cfg=cfg)
    if not url:
        return
    path = upptimerc_path
    with open(path, 'r') as file:
        data = yaml.safe_load(file)
    site = {'name': record, 'url': url}
    url_exists = any(item['url'] == site['url'] for item in data['sites'])
    if not url_exists:
        data['sites'].append(site)
    with open(path, 'w') as file:
        yaml.dump(data, file)


def get_subdomains(content: str) -> List[str]:
    record_type_pattern = r'A\(|ALIAS\(|CNAME\('
    record_name_pattern = r'\("([^"]+)"'
    subdomains = []
    for line in content.split('\n'):
        line = line.strip()
        # Match A( or AAAA( or ALIAS( or CNAME(
        if re.search(record_type_pattern, line):
            # '@' is a placeholder for the apex domain which isn't needed here
            if line.startswith('A("@"') or line.startswith('ALIAS("@"'):
                pass
            else:
                # Match record names in between quotes
                match = re.search(record_name_pattern, line)
                if match:
                    subdomains.append(match.group(1))
    return subdomains


def get_apex_domain(content: str) -> str:
    # Match D( followed by any whitespace, then select apex domain in between quotes
    pattern = r'\bD\(\s*"(.*?)"'
    match = re.search(pattern, content)
    domain = match.group(1) if match else ''
    return domain


def get_upptime_cfg(upptime_cfg: str) -> dict:
    try:
        with open(upptime_cfg, 'r') as yml_file:
            cfg = yaml.safe_load(yml_file)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)
    return cfg


def main(args: argparse.Namespace) -> None:
    cfg = get_upptime_cfg(args.upptime_cfg)
    domain_files = [f for f in os.listdir(args.domains_dir) if f.endswith('.js')]
    for file in domain_files:
        try:
            with open(f"{args.domains_dir}/{file}", 'r') as f:
                content = f.read()
                apex_domain = get_apex_domain(content)
                if not apex_domain or is_ignored(url=apex_domain, cfg=cfg):
                    continue
                upptimerc_path = args.upptimerc_path
                process_record(
                    apex_domain=apex_domain,
                    subdomain='',
                    cfg=cfg,
                    upptimerc_path=upptimerc_path
                )

                subdomains = get_subdomains(content)
                for subdomain in subdomains:
                    process_record(
                        apex_domain=apex_domain,
                        subdomain=subdomain,
                        cfg=cfg,
                        upptimerc_path=upptimerc_path
                    )
        except Exception as e:
            print(f"Error processing file {file}: {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate Upptime sites from records found in DNSControl domain files.'
    )
    parser.add_argument(
        '--domains-dir',
        type=str,
        required=True,
        help='Directory containing DNSControl domain files',
    )
    parser.add_argument(
        '--upptime-cfg',
        type=str,
        required=True,
        help='Configuration file in YAML format',
    )
    parser.add_argument(
        '--upptimerc-path',
        type=str,
        required=True,
        help='Path to .upptimerc.yml',
    )
    args = parser.parse_args()
    main(args)
