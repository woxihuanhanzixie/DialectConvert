import sys
import time
from pathlib import Path
sys.path.insert(0, r"D:\Competition\FireRedASR2S")
from web_demo.app import build_demo

url_file = Path(r"D:\Competition\FireRedASR2S\runtime_data\web_demo_preview\codex_share_url.txt")

demo = build_demo()
launched = demo.launch(server_name="0.0.0.0", server_port=7862, share=True, prevent_thread_lock=True)
local_url = ""
share_url = ""
if isinstance(launched, tuple):
    if len(launched) > 1:
        local_url = str(launched[1] or "")
    if len(launched) > 2:
        share_url = str(launched[2] or "")
else:
    local_url = str(getattr(launched, "local_url", "") or "")
    share_url = str(getattr(launched, "share_url", "") or "")
url_file.write_text(f"local_url={local_url}\nshare_url={share_url}\n", encoding="utf-8")
print(f"local_url={local_url}", flush=True)
print(f"share_url={share_url}", flush=True)
while True:
    time.sleep(3600)
