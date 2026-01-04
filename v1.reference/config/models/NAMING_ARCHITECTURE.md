# Dynamic Configuration System Architecture

## File Naming Convention

**Pattern**: `{provider}_{model_identifier}.json`

**Examples**:

- `ollama_mistral_7b.json` (instead of `ollama_mistral:7b`)
- `ollama_llama3_8b.json`
- `openai_gpt4.json`
- `anthropic_claude3_sonnet.json`
- `stability_stable_diffusion_xl.json`

**Key Principle**: **Content-Driven Processing, Not Filename-Driven**

The filename is purely for human organization. The system discovers and processes configurations based on the JSON content, specifically the `"provider"` field.

## Content-Driven Discovery Process

```python
class DynamicRegistryManager:
    """Dynamically loads provider configs based on JSON content, not filenames."""

    def discover_providers(self) -> Dict[str, Dict[str, Any]]:
        """Scan models directory and organize by provider from JSON content."""
        providers = {}

        for json_file in self.models_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    config = json.load(f)

                # Get provider from JSON content, NOT filename
                provider_name = config.get("provider")
                if not provider_name:
                    logger.warning(f"Config {json_file.name} missing 'provider' field, skipping")
                    continue

                # Initialize provider group if needed
                if provider_name not in providers:
                    providers[provider_name] = {"configs": []}

                # Add this config to the provider group
                config["_config_file"] = json_file.name  # Track source file
                providers[provider_name]["configs"].append(config)

            except Exception as e:
                logger.error(f"Failed to load config {json_file.name}: {e}")
                continue

        return providers
```

## Benefits of This Approach

1. **User Freedom**: Users can name files however they want:
   - `my_favorite_ollama.json`
   - `production_openai.json`
   - `experimental_claude.json`

2. **Content Authority**: Only the JSON content matters for processing

3. **Multi-Model Support**: Multiple configs per provider:
   - `ollama_llama3_8b.json`
   - `ollama_mistral_7b.json`
   - `ollama_codellama_13b.json`

4. **Cross-Platform**: No special characters in filenames

5. **Organization**: Clear naming helps users organize their configs
