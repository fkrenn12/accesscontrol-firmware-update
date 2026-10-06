import uasyncio as asyncio
from config.device_config_defaults import defaults
from networking import https_async_request as https_async
from utils.log import dtprint
from utils.security import encode
import json
from micropython import const as _const_

_HTTP_STATUS_OK = _const_(200)


async def download(secure_download_url, token):
    if not secure_download_url:
        return 0, dict()
    url_encoded_mac = encode(defaults.MAC)
    url_encoded_token = encode(token)
    query = f'mac={url_encoded_mac}&token={url_encoded_token}'
    url = f'{secure_download_url}?{query}'  # removed #
    dtprint(f'INFO: Download-URI {url}')
    res_async = await asyncio.wait_for(https_async.request({'method': 'GET', 'url': url}), timeout=10)
    status_code = res_async.get('status').get('code')
    body = res_async['body']
    downloaded_data = json.loads(body)
    try:
        downloaded_data = downloaded_data[0]
    except:
        pass

    return status_code, downloaded_data


async def upload(secure_upload_url, token, data):
    if not secure_upload_url:
        return 0
    url_encoded_mac = encode(defaults.MAC)
    url_encoded_token = encode(token)
    url = f'{secure_upload_url}?mac={url_encoded_mac}&token={url_encoded_token}'  # removed #
    dtprint(f'INFO: Upload-URI {url}')
    print('UPLOAD data', data)
    res_async = await asyncio.wait_for(https_async.request({'method': 'POST', 'body': data, 'url': url}), timeout=10)
    return res_async.get('status').get('code')
