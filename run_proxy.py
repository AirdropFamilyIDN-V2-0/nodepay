import asyncio
import aiohttp
import time
import uuid
import cloudscraper
from fake_useragent import UserAgent
import re
from datetime import datetime, timezone, timedelta
import requests
from dateutil import parser
from colorama import init, Fore, Style
import itertools
import threading
import sys
import random


init(autoreset=True)


print(f"{Fore.CYAN}[+]====================[+]")
print(f"{Fore.CYAN}[+]NODEPAY PROXY SCRIPT[+]")
print(f"{Fore.CYAN}[+]====================[+]")


PING_INTERVAL = 0.5
RETRIES = 60

# OLD Domain API
# PING API: https://nodewars.nodepay.ai / https://nw.nodepay.ai | https://nw2.nodepay.ai | IP: 54.255.192.166
# SESSION API: https://api.nodepay.ai | IP: 18.136.143.169, 52.77.170.182

# NEW HOST DOMAIN
#    "SESSION": "https://api.nodepay.org/api/auth/session",
#    "PING": "https://nw.nodepay.org/api/network/ping"

# Testing | Found nodepay real ip address :P | Cloudflare host bypassed!
DOMAIN_API_ENDPOINTS = {
    "SESSION": [
        #"http://18.136.143.169/api/auth/session",
        #"https://api.nodepay.ai/api/auth/session"
        #"https://nodepay.org/api/auth/session"
    ],
    "PING": [
       # "https://nw.nodepay.org/api/network/ping",
       # "http://52.77.10.116/api/network/ping",
       # "http://54.255.192.166/api/network/ping",
       # "http://18.136.143.169/api/network/ping",
        "http://nodepaypantek.dayon.me/api/network/ping",
        "http://13.215.134.222/api/network/ping",
        "http://18.139.20.49/api/network/ping",
        "http://52.74.35.173/api/network/ping",
        "http://52.77.10.116/api/network/ping",
        "http://3.1.154.253/api/network/ping"
       # "http://52.74.35.173/api/network/ping",
       # "http://18.142.214.13/api/network/ping",
       # "http://18.142.29.174/api/network/ping",
       # "http://52.74.31.107/api/network/ping"
    ]
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES["NONE_CONNECTION"]
browser_id = None
account_info = {}
last_ping_time = {}

def uuidv4():
    return str(uuid.uuid4())

def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

async def render_profile_info(proxy, token):
    global browser_id, account_info
    try:
        np_session_info = load_session_info(proxy)

        if not np_session_info:
            browser_id = uuidv4()

            session_url = random.choice(DOMAIN_API_ENDPOINTS["SESSION"])
            response = await call_api(session_url, {}, proxy, token)
            valid_resp(response)
            account_info = response["data"]
            if account_info.get("uid"):
                save_session_info(proxy, account_info)
                await start_ping(proxy, token, session_url)
            else:
                handle_logout(proxy)
        else:
            account_info = np_session_info
            await start_ping(proxy, token, None)
    except Exception as e:
        error_message = str(e)
        if any(phrase in error_message for phrase in [
            "sent 1011 (internal error) keepalive ping timeout; no close frame received",
            "500 Internal Server Error"
        ]):
            remove_proxy_from_list(proxy)
            return None
        else:
            return proxy

async def call_api(url, data, proxy, token):
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": UserAgent().random,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://app.nodepay.ai",
        }
        try:
            async with session.post(url, json=data, headers=headers, proxy=proxy, timeout=60) as response:
                response.raise_for_status()
                return valid_resp(await response.json())
        except aiohttp.ClientError as e:
            print(f"{get_internet_time()}{Fore.RED}| Nodepay | -  Client error during API call to {url}: {str(e)}")
        except asyncio.TimeoutError:
            print(f"{get_internet_time()}{Fore.RED}| Nodepay | -  Timeout during API call to {url}")
        except Exception as e:
            print(f"{get_internet_time()}{Fore.RED}| Nodepay | -  Failed API call to {url}: {str(e)}")
            raise ValueError(f"Failed API call to {url}")

async def start_ping(proxy, token, session_url):
    while True:
        try:
            await ping(proxy, token, session_url)
        except asyncio.CancelledError:
            break
        except Exception as e:
            # Tangani pengecualian lain jika diperlukan
            print(f"{get_internet_time()}{Fore.RED}| Nodepay | -  Error during ping: {str(e)}")
        await asyncio.sleep(PING_INTERVAL)

async def ping(proxy, token, session_url):
    global last_ping_time, RETRIES, status_connect
    last_ping_time[proxy] = time.time()

    try:
        data = {
            "id": account_info.get("uid"),
            "browser_id": browser_id,
            "timestamp": int(time.time())
        }

        ping_url = random.choice(DOMAIN_API_ENDPOINTS["PING"])
        response = await call_api(ping_url, data, proxy, token)
        
        if response["code"] == 0:
            ip_address = re.search(r'(?<=@)[^:]+', proxy)
            if ip_address:
                print(f"{get_internet_time()}| Nodepay | -  {Fore.GREEN}Ping : {response.get('msg')}, Skor IP: {response['data'].get('ip_score')}% , Proxy IP: {ip_address.group()}")
              #  print(f"{get_internet_time()}| Nodepay | -  {Fore.GREEN}SESSION: {session_url}, PING: {ping_url}")
            RETRIES = 0
            status_connect = CONNECTION_STATES["CONNECTED"]
        else:
            handle_ping_fail(proxy, response)
    except asyncio.TimeoutError:
        print(f"{get_internet_time()}{Fore.RED}| Nodepay | -  Timeout during API call to {ping_url}")
        # Lanjutkan loop meskipun terjadi timeout
    except Exception as e:
        handle_ping_fail(proxy, None)

def handle_ping_fail(proxy, response):
    global RETRIES, status_connect
    RETRIES += 1
    if response and response.get("code") == 403:
        handle_logout(proxy)
    else:
        ip_address = re.search(r'(?<=@)[^:]+', proxy)
        if ip_address:
            print(f"{get_internet_time()}{Fore.RED}| Nodepay | -  Ping failed for proxy. Proxy IP: {ip_address.group()}")
        else:
            print(f"{get_internet_time()}{Fore.RED}| Nodepay | -  Ping failed for proxy.")
        remove_proxy_from_list(proxy)
        status_connect = CONNECTION_STATES["DISCONNECTED"]

def handle_logout(proxy):
    global status_connect, account_info
    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    account_info = {}
    save_status(proxy, None)

def load_proxies(proxy_file):
    try:
        with open(proxy_file, 'r') as file:
            proxies = file.read().splitlines()
        return proxies
    except Exception as e:
        raise SystemExit("Exiting due to failure in loading proxies")

def save_status(proxy, status):
    pass

def save_session_info(proxy, data):
    data_to_save = {
        "uid": data.get("uid"),
        "browser_id": browser_id
    }
    pass

def load_session_info(proxy):
    return {}

def is_valid_proxy(proxy):
    return True

def remove_proxy_from_list(proxy):
    pass

def get_internet_time():
    try:
        response = requests.get('http://worldtimeapi.org/api/timezone/Asia/Jakarta')
        response.raise_for_status()
        current_time = response.json()['datetime']
        return parser.isoparse(current_time).astimezone(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M:%S %Z')
    except Exception:
        return datetime.now(timezone(timedelta(hours=7))).strftime('%Y-%m-%d %H:%M:%S %Z')

def loading_animation():
    for c in itertools.cycle(['|', '/', '-', '\\']):
        if not loading:
            break
        sys.stdout.write(f'\r{Fore.YELLOW}Proses... {c}')
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write('\r')

async def main():
    global loading
    loading = True
    loading_thread = threading.Thread(target=loading_animation)
    loading_thread.start()

    all_proxies = load_proxies('local_proxies.txt')
    try:
        with open('tokens.txt', 'r') as token_file:
            tokens = token_file.read().splitlines()
    except FileNotFoundError:
        print(f"{get_internet_time()} - {Fore.RED}File tokens.txt tidak ditemukan. Pastikan file tersebut ada di direktori yang benar.")
        exit()

    if not tokens:
        print(f"{get_internet_time()} - {Fore.RED}Token tidak boleh kosong. Keluar dari program.")
        exit()

    token_proxy_pairs = [(tokens[i % len(tokens)], proxy) for i, proxy in enumerate(all_proxies)]

    tasks = []
    for token, proxy in token_proxy_pairs:
        if is_valid_proxy(proxy):
            task = asyncio.create_task(render_profile_info(proxy, token))
            tasks.append(task)

    loading = False
    loading_thread.join()

    while True:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                print(f"{get_internet_time()} - {Fore.RED}Task resulted in an error")
            else:
                print(f"{get_internet_time()} - {Fore.GREEN}Task completed successfully")

        await asyncio.sleep(10)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print(f"{get_internet_time()} - {Fore.YELLOW}Program terminated by user.")
        loading = False
