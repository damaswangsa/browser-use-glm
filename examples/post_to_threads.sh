#!/bin/bash
# Example: Post to Threads
# Make sure chrome-cdp service is running: sudo systemctl status chrome-cdp

source ~/browser-agent/bin/activate
python ~/browser_agent_runner.py "Open https://www.threads.net and create a new post with text: $1"
