# browser-use-glm

Run [browser-use](https://github.com/browser-use/browser-use) with GLM models (via Z.AI API) on a headless Linux server — including ARM64 (Oracle Cloud, etc). Includes an optional [OpenClaw](https://openclaw.dev) skill so you can control the browser agent via Telegram.

> **Credits:** This project is built on top of [browser-use](https://github.com/browser-use/browser-use) by the browser-use team. All browser automation logic is powered by their library. We just made it work with GLM and headless ARM64 servers.

---

## What this does

- Controls a real Chromium browser using AI (GLM-4.6)
- Works on ARM64 VPS (Oracle Cloud Free Tier, etc)
- Keeps browser sessions persistent (saved logins carry over)
- Exposes browser automation as an OpenClaw skill — controllable via Telegram, WhatsApp, Discord, etc

**Example:** Tell OpenClaw on Telegram *"Post to Threads: Hello from AI! 🤖"* and it posts automatically — no manual login required.

---

## Why GLM + browser-use needs patching

Out of the box, browser-use does **not** work with GLM for two reasons:

**1. GLM does not support vision/image_url**
browser-use sends page screenshots as `image_url` in every message. GLM returns error `1210` because it doesn't support this format. Fix: strip all image content before sending to the API.

**2. GLM returns XML `<tool_call>` format, not JSON**
browser-use expects standard JSON tool calls. GLM-4.6 returns a custom XML format. Fix: patch the response parser to handle GLM's format.

Both fixes are applied via monkey patching at runtime — no forking browser-use required.

---

## Requirements

- Ubuntu 22.04 / 24.04 (tested on ARM64 aarch64)
- Python 3.12+
- ~2GB RAM minimum
- Z.AI API key (free at [z.ai](https://z.ai))
- Optional: [OpenClaw](https://openclaw.dev) for Telegram control

---

## Installation

### 1. Create Python virtual environment

```bash
python3 -m venv ~/browser-agent
source ~/browser-agent/bin/activate
```

### 2. Install browser-use and dependencies

```bash
pip install browser-use==0.1.40 langchain-openai --break-system-packages
playwright install chromium
```

### 3. Apply patches

**Patch 1: Fix `content=None` bug in langchain-openai**

```bash
sed -i 's/message_dict\["content"\] = message_dict\["content"\] or None/message_dict["content"] = message_dict["content"] or ""/' \
  ~/browser-agent/lib/python3.12/site-packages/langchain_openai/chat_models/base.py
```

**Patch 2: Add GLM XML response parser to browser-use**

```bash
sed -i '3a import re' \
  ~/browser-agent/lib/python3.12/site-packages/browser_use/agent/message_manager/utils.py
```

Then inject the GLM parser:

```bash
python3 << 'PATCH'
filepath = '/home/ubuntu/browser-agent/lib/python3.12/site-packages/browser_use/agent/message_manager/utils.py'

glm_block = """        # Handle GLM <tool_call> XML format
        if '<tool_call>' in content:
            m = re.search(r'\\{[\\s\\S]+?"current_state"[\\s\\S]+?"action"[\\s\\S]+?\\}', content)
            if m:
                try: return json.loads(m.group(0))
                except: pass
            cs, ac = {}, []
            cm = re.search(r'"evaluation_previous_goal".*?"next_goal"\\s*:\\s*"[^"]+"', content, re.DOTALL)
            if cm:
                try: cs = json.loads('{' + cm.group(0) + '}')
                except: pass
            am = re.search(r'"action"\\s*[":]+\\s*(\\[[^\\]]*\\])', content, re.DOTALL)
            if am:
                try: ac = json.loads(am.group(1))
                except: pass
            if cs:
                return {'current_state': cs, 'action': ac}
            raise ValueError('Could not parse GLM tool_call')
"""

with open(filepath, 'r') as f:
    content = f.read()

target = 'def extract_json_from_model_output(content: str) -> dict:'
idx = content.find(target)
if idx != -1:
    insert_pos = content.find('\n', content.find('\n', idx) + 1) + 1
    content = content[:insert_pos] + glm_block + content[insert_pos:]
    with open(filepath, 'w') as f:
        f.write(content)
    print("SUCCESS: GLM parser injected")
else:
    print("ERROR: could not find target function")
PATCH
```

### 4. Set up Chrome with persistent profile

Login to your VPS desktop (VNC) and open Chromium manually:

```bash
DISPLAY=:1 ~/.cache/ms-playwright/chromium-1208/chrome-linux/chrome \
  --no-sandbox \
  --user-data-dir=/home/ubuntu/chrome-profile &
```

Log in to Threads (or any site you need) in the browser window on VNC. Close the browser when done.

### 5. Run Chrome as a persistent background service

```bash
sudo tee /etc/systemd/system/chrome-cdp.service << 'EOF'
[Unit]
Description=Chrome CDP for browser-use
After=network.target

[Service]
User=ubuntu
ExecStartPre=-/usr/bin/pkill -f "chrome.*9222"
ExecStartPre=/bin/sleep 1
ExecStartPre=/bin/rm -f /home/ubuntu/chrome-profile/Singleton*
ExecStart=/home/ubuntu/.cache/ms-playwright/chromium-1208/chrome-linux/chrome \
  --no-sandbox --disable-gpu --headless=new \
  --remote-debugging-port=9222 \
  --user-data-dir=/home/ubuntu/chrome-profile \
  --disable-dev-shm-usage
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable chrome-cdp
sudo systemctl start chrome-cdp

# Verify Chrome is running
curl -s http://localhost:9222/json/version | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK:', d['Browser'])"
```

### 6. Set your API key

```bash
export ZAI_API_KEY="your_api_key_here"
```

### 7. Test it

```bash
source ~/browser-agent/bin/activate
python /home/ubuntu/browser_agent_runner.py "Open https://example.com and get the page title"
```

Expected output:

```json
{"success": true, "result": "Successfully opened example.com. Page title: 'Example Domain'"}
```

---

## Posting to Threads

### Single post

```bash
source ~/browser-agent/bin/activate
python /home/ubuntu/browser_agent_runner.py \
  "Open https://www.threads.net and create a new post with text: Hello from AI agent! 🤖"
```

### Thread chains (2+ posts)

For multi-post threads, use `post_thread.py` instead of the AI agent. This script uses Playwright CDP directly — deterministic and reliable for any number of posts.

```bash
source ~/browser-agent/bin/activate
THREADS_USERNAME=yourusername python /home/ubuntu/post_thread.py \
  "First post 🧵" \
  "Second post 🔧" \
  "Third post ✅"
```

Set your username permanently:

```bash
export THREADS_USERNAME="yourusername"
```

> **Why a separate script?** The AI agent (`browser_agent_runner.py`) is unreliable for multi-post threads — it tends to merge posts or fail at post 3+ due to GLM's inconsistent tool call parsing. `post_thread.py` bypasses the AI entirely and controls the Threads composer directly via Playwright.

---

## OpenClaw Skill (optional)

If you use [OpenClaw](https://openclaw.dev), you can control the browser agent via Telegram.

```bash
mkdir -p ~/.openclaw/workspace/skills/browser
```

**`~/.openclaw/workspace/skills/browser/_meta.json`**

```json
{
  "slug": "browser",
  "version": "1.0.0",
  "description": "Control a real Chromium browser for web automation tasks including posting to Threads"
}
```

**`~/.openclaw/workspace/skills/browser/SKILL.md`**

Create this file with the following content:

```
---
name: browser
description: "Control a real Chromium browser. For posting thread chains to Threads (2+ posts), use post_thread.py. For single posts or general browsing, use browser_agent_runner.py."
---

# Browser Automation Skill

## Post Thread Chain (2+ posts)

THREADS_USERNAME=yourusername source /home/ubuntu/browser-agent/bin/activate \
  && python /home/ubuntu/post_thread.py "post 1" "post 2" "post 3"

## Single Post / General Browsing

source /home/ubuntu/browser-agent/bin/activate \
  && python /home/ubuntu/browser_agent_runner.py "TASK HERE"

## Notes
- Chrome CDP service: sudo systemctl status chrome-cdp
- To restart Chrome: sudo systemctl restart chrome-cdp
```

Restart OpenClaw after updating the skill:

```bash
systemctl --user restart openclaw-gateway.service
```

Now you can tell OpenClaw via Telegram:

> *"Post thread to Threads: post 1: 'Hello 🧵' post 2: 'Second post 🔧' post 3: 'Done ✅'"*

---

## Architecture

```
Telegram
  ↓ message
OpenClaw (glm-4.6)
  ↓ reads browser skill, runs command
  ├── post_thread.py          (thread chains — Playwright CDP, deterministic)
  └── browser_agent_runner.py (single tasks — AI agent via GLM-4.6)
        ↓
Chrome :9222 (headless, with saved logins)
        ↓
Any website (Threads, etc) ✅
```

---

## Key files

| File | Purpose |
|------|---------|
| `~/browser-agent/` | Python venv with browser-use |
| `~/browser_agent_runner.py` | AI agent runner for general tasks |
| `~/post_thread.py` | Deterministic thread chain poster (2+ posts) |
| `~/chrome-profile/` | Chrome profile with saved logins |
| `/etc/systemd/system/chrome-cdp.service` | Chrome background service |
| `~/.openclaw/workspace/skills/browser/` | OpenClaw skill |

---

## Troubleshooting

**Error 1210 from GLM API**
The image patch is not applied. Check that `_patched_build` is running before the agent starts.

**`Could not parse GLM tool_call`**
The XML parser patch is not applied. Re-run the utils.py patch script.

**Chrome CDP connection refused**
Chrome service is not running. Run:

```bash
sudo systemctl restart chrome-cdp
curl -s http://localhost:9222/json/version
```

**`SingletonLock` error when starting Chrome**
Another Chrome instance is using the profile. Run:

```bash
rm -f /home/ubuntu/chrome-profile/Singleton*
sudo systemctl restart chrome-cdp
```

**xdotool / xte crashes on ARM64**
This is expected — those tools are unreliable on ARM64. Use this browser-use approach instead.

**OpenClaw not using the browser skill**
Be explicit in your Telegram message, or update the skill `description` to be more specific.

---

## Credits

- [browser-use](https://github.com/browser-use/browser-use) — the core browser automation library this project is built on
- [Z.AI](https://z.ai) — GLM API provider
- [Playwright](https://playwright.dev) — browser driver used by browser-use
- [OpenClaw](https://openclaw.dev) — AI gateway used for Telegram integration

---

## License

MIT
