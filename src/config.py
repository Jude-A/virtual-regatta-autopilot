# config.py
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "races.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    RACES = json.load(f)

CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")

with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
    creds = json.load(f)

MAIL = creds["MAIL"]
MDP = creds["MDP"]

LEG_NUM = 1

# URLs & headers
url_auth = "https://prod.vro.sparks.virtualregatta.com/rs/device/Xcl3WbCUmfcu5pWCktUoC0slGT4xkbEt/AuthenticationRequest"
url_heading = "https://prod.vro.sparks.virtualregatta.com/rs/device/Xcl3WbCUmfcu5pWCktUoC0slGT4xkbEt/LogEventRequest"
url_sail = url_heading
url_getboatinfos = "https://vro-api-client.prod.virtualregatta.com/getboatinfos"

common_headers = {
    "accept": "application/json",
    "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "dnt": "1",
    "origin": "https://play.offshore.virtualregatta.com",
    "priority": "u=1, i",
    "referer": "https://play.offshore.virtualregatta.com/",
    "sec-ch-ua": "\"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "x-platform": "WebGLPlayer",
    "x-version": "7.0.9"
}

headers_auth = common_headers.copy()
headers_heading = common_headers.copy()
headers_sail = common_headers.copy()
headers_getboatinfos = common_headers.copy()
headers_getboatinfos.update({
    "x-api-key": "WL5V/Ck9oPF4RClVbCzk0pBXGnrTrrtMFTCnxn4de3c=",
    "x-playerid": "59dbaacfe7821e29549201de",
})