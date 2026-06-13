from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from benchsvc.llm_client import DataEyesClient
from benchsvc.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="generated/litellm.config.yaml")
    parser.add_argument("--no-discovery", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    model_ids: list[str] = []

    if settings.allowlist:
        model_ids = [m.removeprefix("dataeyes/") for m in settings.allowlist]
    elif settings.dataeyes_default_model:
        model_ids = [settings.dataeyes_default_model]

    if not model_ids and not args.no_discovery and settings.dataeyes_api_key:
        try:
            model_ids = [m.id for m in DataEyesClient(settings).list_models(include_raw=False)]
        except Exception as exc:
            print(f"warning: discovery failed while generating LiteLLM config: {exc}")

    if not model_ids:
        # Keep proxy bootable after first init; user should set DATAEYES_DEFAULT_MODEL or API key.
        model_ids = ["replace-with-dataeyes-model-id"]

    max_models = max(1, settings.max_models_per_run)
    model_ids = model_ids[:max_models]

    config = {
        "general_settings": {"master_key": "os.environ/LITELLM_MASTER_KEY"},
        "model_list": [],
        "litellm_settings": {"callbacks": ["langfuse_otel"], "set_verbose": False},
    }
    for model_id in model_ids:
        config["model_list"].append(
            {
                "model_name": f"dataeyes/{model_id}",
                "litellm_params": {
                    "model": f"openai/{model_id}",
                    "api_base": "os.environ/DATAEYES_LLM_BASE_URL",
                    "api_key": "os.environ/DATAEYES_API_KEY",
                },
            }
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"wrote {output} with {len(model_ids)} model mapping(s)")


if __name__ == "__main__":
    main()
