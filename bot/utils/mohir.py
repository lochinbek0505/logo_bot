import requests
import os
from dotenv import load_dotenv
from io import BytesIO
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

def try_3(url, headers, files, data):
    try:
        response = requests.post(
            url,
            headers=headers,
            files=files,
            data=data,
            verify=False  # SSL ogohlantiruvchi xabarlar uchun
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"[ERROR] Status: {response.status_code}, Body: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"[EXCEPTION] {e}")
        return False

def stt(content: bytes, api_key=os.getenv("mohirAi")):
    url = 'https://uzbekvoice.ai/api/v1/stt'
    headers = {
        "Authorization": api_key,
        # NOTE: requests avtomatik multipart type yuboradi, shuning uchun bu headerni o‘chiramiz
    }

    files = {
        "file": ("audio.mp3", BytesIO(content), "audio/mpeg")
    }
    data = {
        "return_offsets": "true",
        "run_diarization": "false",
        "language": "uz",
        "blocking": "true",
    }

    for _ in range(3):
        res = try_3(url, headers, files, data)
        if res:
            return res

    return {"result": {"text": ""}}  # fallback
