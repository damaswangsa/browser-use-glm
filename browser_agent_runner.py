#!/usr/bin/env python3
import asyncio, sys, json, subprocess, time, os

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

CHROME = os.path.expanduser('~/.cache/ms-playwright/chromium-1208/chrome-linux/chrome')
CDP_PORT = 9222

def start_chrome():
    proc = subprocess.Popen([
        CHROME,
        '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
        '--headless=new',
        f'--remote-debugging-port={CDP_PORT}',
        '--user-data-dir=/home/ubuntu/chrome-profile',
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    return proc

async def main(task: str):
    chrome_proc = start_chrome()
    try:
        llm = ChatOpenAI(
            base_url='https://api.z.ai/api/coding/paas/v4/',
            api_key='a23ce80df82e4d76ac679c9742d0e5f9.0j6TSHbYWvw1nyC7',
            model='glm-4.6'
        )
        browser = Browser(config=BrowserConfig(
            cdp_url=f'http://localhost:{CDP_PORT}',
            extra_chromium_args=['--no-sandbox','--disable-gpu','--disable-dev-shm-usage']
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
    finally:
        chrome_proc.terminate()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No task provided"}))
        sys.exit(1)
    task = ' '.join(sys.argv[1:])
    asyncio.run(main(task))
