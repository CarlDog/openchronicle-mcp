# Plugin quickstart

See the plugin contract for guarantees and requirements: [plugin_contract.md](plugin_contract.md)

## Structure

Plugins live under the top-level plugins/ directory. Each plugin must be a package with **init**.py and a plugin.py entrypoint:

```text
plugins/
  hello_plugin/
    __init__.py
    plugin.py
```

## Entry point

Implement a register() function in plugin.py that receives the PluginRegistry and TaskHandlerRegistry:

- register a task handler with a deterministic handler name (namespace.action)
- avoid external dependencies

## Run locally

```bash
python -m pytest
```

```bash
oc selftest --json
```

## Run in Docker

```bash
docker build -t openchronicle-core:local .
```

```bash
docker run --rm openchronicle-core:local selftest --json
```

## Invoke the hello plugin

Use task_type = plugin.invoke with a payload that specifies the handler and input:

```bash
# 1) Create a project
PROJECT_ID=$(oc init-project "plugin-demo")

# 2) Submit a plugin invocation task
TASK_ID=$(oc rpc --request '{"protocol_version":"1","command":"task.submit","args":{"project_id":"'"$PROJECT_ID"'","task_type":"plugin.invoke","payload":{"handler":"hello.echo","input":{"prompt":"hello"}}}}' | jq -r '.result.task_id')

# 3) Execute queued tasks
oc rpc --request '{"protocol_version":"1","command":"task.run_many","args":{"limit":5,"type":"plugin.invoke","max_seconds":0}}'

# 4) Read the result
oc show-task --result "$TASK_ID"
```
