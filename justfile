run:
    uv run streamlit run src/main.py

# Run the example receiver; override host and port to expose it on your network.
receiver host="127.0.0.1" port="8000":
    uv run uvicorn receiver:app --app-dir src --host {{quote(host)}} --port {{quote(port)}}
