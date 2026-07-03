"""Managed Codex profile fragments for the optional cost router."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostRoutingProfiles:
    """Rendered TOML fragments written by codex_cost_router.py."""

    managed_block: str
    litellm_profile: str
    huggingface_profile: str


def render_profiles(default_model: str, hf_direct_model: str) -> CostRoutingProfiles:
    """Return Codex TOML profiles for LiteLLM and Hugging Face routing."""
    managed_block = f"""\
# BEGIN CODEX COST ROUTER
[model_providers.litellm]
name = "LiteLLM OSS Cost Router"
base_url = "http://localhost:4000/v1"
env_key = "LITELLM_API_KEY"

[model_providers.huggingface]
name = "Hugging Face Inference Providers"
base_url = "https://router.huggingface.co/v1"
env_key = "HF_TOKEN"
wire_api = "chat"

[profiles.cost-routing]
model = "{default_model}"
model_provider = "litellm"
model_reasoning_effort = "medium"
model_verbosity = "low"
model_auto_compact_token_limit = 64000
tool_output_token_limit = 8000

[profiles.cost-routing-hf]
model = "{hf_direct_model}"
model_provider = "huggingface"
model_reasoning_effort = "low"
# END CODEX COST ROUTER
"""

    litellm_profile = f"""\
model = "{default_model}"
model_provider = "litellm"
model_reasoning_effort = "medium"
model_verbosity = "low"
model_auto_compact_token_limit = 64000
tool_output_token_limit = 8000

[model_providers.litellm]
name = "LiteLLM OSS Cost Router"
base_url = "http://localhost:4000/v1"
env_key = "LITELLM_API_KEY"
wire_api = "chat"
"""

    huggingface_profile = f"""\
model = "{hf_direct_model}"
model_provider = "huggingface"
model_reasoning_effort = "low"

[model_providers.huggingface]
name = "Hugging Face Inference Providers"
base_url = "https://router.huggingface.co/v1"
env_key = "HF_TOKEN"
wire_api = "chat"
"""

    return CostRoutingProfiles(
        managed_block=managed_block,
        litellm_profile=litellm_profile,
        huggingface_profile=huggingface_profile,
    )
