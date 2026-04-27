import json
import requests
urls = [
  'https://download.pytorch.org/whl/cu129/torch-2.11.0%2Bcu129-cp310-cp310-win_amd64.whl',
  'https://download.pytorch.org/whl/cu129/torchvision-0.24.0%2Bcu129-cp310-cp310-win_amd64.whl',
  'https://download.pytorch.org/whl/cu129/torchaudio-2.11.0%2Bcu129-cp310-cp310-win_amd64.whl',
]
out = []
for u in urls:
    try:
        r = requests.head(u, timeout=30, allow_redirects=True)
        out.append({'url': u, 'status': r.status_code, 'len': int(r.headers.get('Content-Length', '0') or 0)})
    except Exception as e:
        out.append({'url': u, 'status': 'ERR', 'err': str(e)})
print(json.dumps(out, ensure_ascii=False, indent=2))
