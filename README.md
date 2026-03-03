# browser-use-glm

Run [browser-use](https://github.com/browser-use/browser-use) with GLM models (via Z.AI API) on a headless Linux server — including ARM64 (Oracle Cloud, etc). Includes an optional [OpenClaw](https://openclaw.dev) skill so you can control the browser agent via Telegram.

> **Credits:** This project is built on top of [browser-use](https://github.com/browser-use/browser-use) by the browser-use team. All browser automation logic is powered by their library. We just made it work with GLM and headless ARM64 servers.

---

## What this does

- Controls a real Chromium browser using AI (GLM-4.6)
- Works on ARM64 VPS (Oracle Cloud Free Tier, etc)
- Keeps browser sessions persistent (saved logins carry over)
- Exposes browser automation as an OpenClaw skill — controllable via your openclaw channel (Whatsapp, Telegram, Discord, etc)

**Example:** Tell OpenClaw on Telegram _"Post to Threads: Hello from AI! 🤖"_ and it posts automatically — no manual login required.

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
# Add 'import re' after existing imports
sed -i '3a import re' \
  ~/browser-agent/lib/python3.12/site-packages/browser_use/agent/message_manager/utils.py
```

Then run this Python script to inject the GLM parser:

```bash
python3 << 'EOF'
filepath = '/home/ubuntu/browser-agent/lib/python3.12/site-packages/browser_use/agent/message_manager/utils.py'

with open(filepath, 'r') as f:
    content = f.read()

old = "\t\t# Handle GLM <tool_call> XML format\n\t\tif '<tool_call>' in content:\n\t\t\tcurrent_state = {}\n\t\t\taction = []\n\t\t\tfor key_match in re.finditer(r'<arg_key>(.*?)</arg_key>\\s*<arg_value>(.*?)</arg_value>', content, re.DOTALL):\n\t\t\t\tk, v = key_match.group(1).strip(), key_match.group(2).strip()\n\t\t\t\tif k == 'current_state':\n\t\t\t\t\tcurrent_state = json.loads(v)\n\t\t\t\telif k == 'action':\n\t\t\t\t\taction = json.loads(v)\n\t\t\treturn {'current_state': current_state, 'action': action}"

new = "\t\t# Handle GLM <tool_call> XML format\n\t\tif '<tool_call>' in content:\n\t\t\t# Try full JSON first\n\t\t\tm = re.search(r'\\{[\\s\\S]+?\"current_state\"[\\s\\S]+?\"action\"[\\s\\S]+?\\}', content)\n\t\t\tif m:\n\t\t\t\ttry: return json.loads(m.group(0))\n\t\t\t\texcept: pass\n\t\t\t# Extract parts separately\n\t\t\tcs, ac = {}, []\n\t\t\tcm = re.search(r'\"evaluation_previous_goal\".*?\"next_goal\"\\s*:\\s*\"[^\"]+\"', content, re.DOTALL)\n\t\t\tif cm:\n\t\t\t\ttry: cs = json.loads('{' + cm.group(0) + '}')\n\t\t\t\texcept: pass\n\t\t\tam = re.search(r'\"action\"\\s*[\":]+\\s*(\\[[^\\]]*\\])', content, re.DOTALL)\n\t\t\tif am:\n\t\t\t\ttry: ac = json.loads(am.group(1))\n\t\t\t\texcept: pass\n\t\t\tif cs:\n\t\t\t\treturn {'current_state': cs, 'action': ac}\n\t\t\traise ValueError('Could not parse GLM tool_call')"

if old in content:
    content = content.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(content)
    print("SUCCESS: GLM parser injected")
else:
    # Fresh install - insert before existing try block
    insert_after = 'def extract_json_from_model_output(content: str) -> dict:'
    glm_block = '\n\t\t# Handle GLM <tool_call> XML format\n\t\tif \'<tool_call>\' in content:\n\t\t\tm = re.search(r\'\\{[\\s\\S]+?"current_state"[\\s\\S]+?"action"[\\s\\S]+?\\}\', content)\n\t\t\tif m:\n\t\t\t\ttry: return json.loads(m.group(0))\n\t\t\t\texcept: pass\n\t\t\tcs, ac = {}, []\n\t\t\tcm = re.search(r\'"evaluation_previous_goal".*?"next_goal"\\s*:\\s*"[^"]+"\', content, re.DOTALL)\n\t\t\tif cm:\n\t\t\t\ttry: cs = json.loads(\'{\' + cm.group(0) + \'}\')\n\t\t\t\texcept: pass\n\t\t\tam = re.search(r\'"action"\\s*[":]+\\s*(\\[[^\\]]*\\])\', content, re.DOTALL)\n\t\t\tif am:\n\t\t\t\ttry: ac = json.loads(am.group(1))\n\t\t\t\texcept: pass\n\t\t\tif cs:\n\t\t\t\treturn {\'current_state\': cs, \'action\': ac}\n\t\t\traise ValueError(\'Could not parse GLM tool_call\')\n'
    print("NOTE: Could not find existing block. Check utils.py manually.")
EOF
```

### 4. Set up Chrome with persistent profile

Login to your VPS desktop (VNC) and open Chromium manually with a profile directory:

```bash
# From SSH terminal, opens Chromium on VNC display :1
DISPLAY=:1 ~/.cache/ms-playwright/chromium-1208/chrome-linux/chrome \
  --no-sandbox \
  --user-data-dir=/home/ubuntu/chrome-profile &
```

Log in to Threads (or any site you need) manually in the browser window on VNC. Close the browser when done.

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

### 6. Create the runner script

Save this as `/home/ubuntu/browser_agent_runner.py`:

```python
#!/usr/bin/env python3
"""
browser-use-glm runner
Connects browser-use to GLM-4.6 via Z.AI API with patches for:
- image_url filtering (GLM does not support vision)
- XML tool_call response parsing (GLM returns XML, not JSON)
- Persistent Chrome session via CDP
"""
import asyncio, sys, json, subprocess, time, os

# Patch 1: Strip image_url from messages before sending to GLM
import openai._base_client as obc
_orig_build = obc.BaseClient._build_request

def _patched_build(self, options, *args, **kwargs):
    if isinstance(options.json_data, dict) and 'messages' in options.json_data:
        new_messages = []
        for m in options.json_data['messages']:
            if isinstance(m.get('content'), list):
                text_parts = [p for p in m['content'] if p.get('type') == 'text']
                m = dict(m)
                m['content'] = text_parts[0]['text'] if text_parts else ''
            new_messages.append(m)
        options.json_data = dict(options.json_data)
        options.json_data['messages'] = new_messages
    return _orig_build(self, options, *args, **kwargs)

obc.BaseClient._build_request = _patched_build

from browser_use import Agent, Browser, BrowserConfig
from langchain_openai import ChatOpenAI

CDP_PORT = 9222

async def main(task: str):
    llm = ChatOpenAI(
        base_url='https://api.z.ai/api/coding/paas/v4/',
        api_key=os.environ.get('ZAI_API_KEY', 'YOUR_API_KEY_HERE'),
        model='glm-4.6'
    )
    browser = Browser(config=BrowserConfig(
        cdp_url=f'http://localhost:{CDP_PORT}',
        extra_chromium_args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
    ))
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        tool_calling_method='raw'
    )
    result = await agent.run()
    final = result.final_result() if hasattr(result, 'final_result') else str(result)
    print(json.dumps({"success": True, "result": final}))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No task provided"}))
        sys.exit(1)
    task = ' '.join(sys.argv[1:])
    asyncio.run(main(task))
```

Set your API key:

```bash
export ZAI_API_KEY="your_api_key_here"
# Or hardcode it in the script
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

## Post to Threads

Since you logged in during step 4, the session is saved. Just run:

```bash
source ~/browser-agent/bin/activate
python /home/ubuntu/browser_agent_runner.py \
  "Open https://www.threads.net and create a new post with text: Hello from AI agent! 🤖"
```

---

## OpenClaw Skill (optional)

If you use [OpenClaw](https://openclaw.dev), you can control the browser agent via Telegram.

Create the skill directory and files:

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
```markdown
---
name: browser
description: "Control a real Chromium browser to automate web tasks. Use for posting to Threads, browsing websites, filling forms, or extracting web content. Do NOT use xdotool, xte, wmctrl, or firefox. Threads is already logged in."
---

# Browser Automation Skill

## Command

\`\`\`bash
source /home/ubuntu/browser-agent/bin/activate && python /home/ubuntu/browser_agent_runner.py "TASK HERE"
\`\`\`

## Examples

Post to Threads:
\`\`\`bash
source /home/ubuntu/browser-agent/bin/activate && python /home/ubuntu/browser_agent_runner.py "Open https://www.threads.net and create a new post with text: YOUR TEXT HERE"
\`\`\`

Browse and extract:
\`\`\`bash
source /home/ubuntu/browser-agent/bin/activate && python /home/ubuntu/browser_agent_runner.py "Open https://techcrunch.com/category/artificial-intelligence/ and get the 5 latest headlines"
\`\`\`

## Notes
- Chrome profile with Threads login: /home/ubuntu/chrome-profile
- Chrome CDP service: sudo systemctl status chrome-cdp
- To restart Chrome: sudo systemctl restart chrome-cdp
```

Then restart OpenClaw:
```bash
systemctl --user restart openclaw-gateway.service
```

Now you can tell OpenClaw via Telegram:
> _"Post to Threads: Hello from OpenClaw! 🦞"_

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
Be explicit in your Telegram message, e.g.:
> _"Use the browser skill to post to Threads: [your text]"_

Or update the skill's `description` field to be more specific.

---

## Architecture

```
Telegram
  ↓ message
OpenClaw (glm-4.6)
  ↓ reads browser skill, runs command
browser_agent_runner.py
  ↓ connects via CDP
Chrome :9222 (headless, with saved logins)
  ↓ controls browser
Any website (Threads, etc) ✅
```

---

## Key files

| File | Purpose |
|------|---------|
| `~/browser-agent/` | Python venv with browser-use |
| `~/browser_agent_runner.py` | Main runner script |
| `~/chrome-profile/` | Chrome profile with saved logins |
| `/etc/systemd/system/chrome-cdp.service` | Chrome background service |
| `~/.openclaw/workspace/skills/browser/` | OpenClaw skill |

---

## Credits

- [browser-use](https://github.com/browser-use/browser-use) — the core browser automation library this project is built on
- [Z.AI](https://z.ai) — GLM API provider
- [Playwright](https://playwright.dev) — browser driver used by browser-use
- [OpenClaw](https://openclaw.dev) — AI gateway used for Telegram integration

---

## License

MIT
