@echo off
set "GROQ_API_KEY=%GROQ_API_KEY%"
set "PRISMEDGE_AGENT_MODEL=llama-3.3-70b-versatile"
set "PRISMEDGE_AGENT_API_URL=https://api.groq.com/openai/v1/chat/completions"
call start_api.bat
