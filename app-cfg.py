#!/usr/bin/env python3

import shutil
import sys
import filecmp
import json
import logging
import os
import requests
import schema


#===== Variables and Constants =================================================

CFG_SCHEMA = schema.Schema(
    schema.And(
        # JSON expected
        schema.Use(json.loads),
        # The schema itself
        {
            'api_url': schema.Use(str),
            'tls_ca': schema.Use(str),
            'tls_crl': schema.Use(str),
            'tls_crt': schema.Use(str),
            'tls_key': schema.Use(str),
            schema.Optional('log_level'):
                schema.Regex(r'^(debug|info|warning|error|critical)$'),
        }))

DIR_APP = '/opt/app-cfg'
FILEPATH_CFG = f"{DIR_APP}/app-cfg.json"

TARGET_APP_NAME = 'myapp'
TARGET_APP_CFG_PATH = '/opt/myapp/myapp.cfg'


#===== Methods =================================================================

#----- Configuration -----------------------------------------------------------
# Loads, validates and returns main configuration
def load_cfg(cfg_fname, cfg_schema):
    with open(cfg_fname, encoding='utf-8') as f: # pylint: disable=W0621
        cfg_raw = f.read()
    try:
        cfg = cfg_schema.validate(cfg_raw)  # pylint: disable=W0621
    except Exception as e:
        raise schema.SchemaError(e)
    return cfg

# Fetches data from API
def fetch_api_data(cfg, app_name):
    api_url = f"{cfg['api_url']}/cfg"
    logging.debug(f"[{app_name}] api_url={api_url}")
    response = requests.get(
        api_url,
        verify=cfg['tls_ca'],
        cert=(cfg['tls_crt'], cfg['tls_key']))

    if response.status_code != 200:
        logging.error(
            f"[{app_name}] Cannot get data from API, "
            f"code={response.status_code}")
        sys.exit(1)

    api_data = response.json()
    api_status = api_data.get('success', 'unknown')
    if api_status != 'ok':
        logging.error(
            f"[{app_name}] API returned unexpected success={api_status}")
        sys.exit(1)
    logging.info(
        f"[{app_name}] Successfully fetched data from API")
    logging.debug(f"[{app_name}] api_data={api_data}")

    return api_data

# Compares new configuration data with the existing one and update if needed
def update_app(app_cfg_path, api_data):
    success = True

    fpath_old = app_cfg_path
    fpath_new = f"{app_cfg_path}.new"
    with open(fpath_new, 'w', encoding='utf-8') as f:
        f.write(f"{api_data}\n")

    if not filecmp.cmp(fpath_old, fpath_new):
        shutil.move(fpath_new, fpath_old)
        logging.info(f"Deployed new '{fpath_old}'")
    else:
        logging.info(f"'{fpath_old}' not changed")
    return success


#===== Main ====================================================================

#----- Configuration -----------------------------------------------------------
# Load main configuration & configure logging
cfg = load_cfg(FILEPATH_CFG, CFG_SCHEMA)
log_levelint = getattr(logging, cfg['log_level'].upper())
logging.basicConfig(
    format='[%(levelname)s] %(message)s', encoding='utf-8', level=log_levelint)
logging.debug(f"cfg = {cfg}")

if os.geteuid() != 0:
    logging.critical('Must be root')
    sys.exit(1)

#----- Main --------------------------------------------------------------------
update_app(TARGET_APP_CFG_PATH, fetch_api_data(cfg, TARGET_APP_NAME))
