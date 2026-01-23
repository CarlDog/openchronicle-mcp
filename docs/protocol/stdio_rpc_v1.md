# OpenChronicle STDIO RPC Protocol v1

## Version

````json
# OpenChronicle STDIO RPC Protocol v1

## Version

protocol_version: "1"

## Overview

The STDIO RPC protocol defines newline-delimited JSON requests sent to `oc serve` and `oc rpc` and JSON responses
written to stdout. Stdout must contain JSON only. Diagnostics must be sent to stderr.

## Request schema

Requests are single JSON objects on one line.

```json
{"protocol_version":"1","command":"...","args":{...}}
```

- `protocol_version` (optional, recommended): must be "1" for this protocol version. If provided and not "1",
  the server responds with `UNSUPPORTED_PROTOCOL_VERSION`.
- `command` (required): string command name.
- `args` (optional): object containing command arguments. Defaults to `{}` when omitted.

## Response envelope

Responses are single JSON objects on one line.

```json
{"protocol_version":"1","command":"...","ok":true,"result":{...},"error":null}
```

- `protocol_version` (optional, recommended): "1".
- `command`: echoes the request command.
- `ok`: boolean success flag.
- `result`: object or `null`.
- `error`: object or `null`.

### Error object

```json
{"error_code":"INVALID_JSON","message":"...","hint":null}
```

- `error_code`: string or `null`.
- `message`: string.
- `hint`: string or `null`.
- `details`: object or `null`.

## Error codes

- `INVALID_JSON`
- `INVALID_REQUEST`
- `INVALID_ARGUMENT`
- `INTERNAL_ERROR`
- `UNKNOWN_COMMAND`
- `NSFW_POOL_NOT_CONFIGURED`
- `UNSUPPORTED_PROTOCOL_VERSION`

## Supported commands

### system.info

Args: `{}`

Result:

```json
{"name":"openchronicle","protocol_version":"1","capabilities":{"serve":true,"rpc":true}}
```

### system.commands

Args: `{}`

Result:

```json
{"commands":["convo.ask","convo.export","convo.mode","convo.show","convo.verify","system.commands","system.info","system.ping","system.shutdown"]}
```

### system.ping

Args: `{}`

Result:

```json
{"pong":true}
```

### system.shutdown

Args: `{}`

Result: `null`

### convo.export

Args:

```json
{"conversation_id":"...","explain":false,"verify":false}
```

Result: the existing export payload.

### convo.verify

Args:

```json
{"conversation_id":"..."}
```

Result:

```json
{"conversation_id":"...","verification":{"ok":true,"failure_event_id":null,"expected_hash":null,"actual_hash":null}}
```

### convo.ask

Args:

```json
{"conversation_id":"...","prompt":"...","last_n":10,"top_k_memory":8,"include_pinned_memory":true,"explain":false}
```

Result:

```json
{"conversation_id":"...","turn_id":"...","turn_index":1,"assistant_text":"...","explain":null}
```

### convo.show

Args:

```json
{"conversation_id":"...","limit":10,"explain":false}
```

Result:

```json
{"conversation_id":"...","mode":"general","turns":[{"turn_id":"...","turn_index":1,"user_text":"...","assistant_text":"...","explain":null}]}
```

### convo.mode

Args (get):

```json
{"conversation_id":"..."}
```

Args (set):

```json
{"conversation_id":"...","mode":"persona"}
```

Result:

```json
{"conversation_id":"...","mode":"persona"}
```
```

Args (set):

```
{"conversation_id":"...","mode":"persona"}
```

Result:

```
{"conversation_id":"...","mode":"persona"}
```
````
