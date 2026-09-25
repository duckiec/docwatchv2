import re
from typing import List, Union

def mask_sensitive_env_vars(env_list: Union[List[str], dict]) -> List[str]:
    """
    Masks sensitive values in a list of environment variables.
    Handles 'KEY=VALUE' format.
    """
    sensitive_keys = re.compile(
        r'password|secret|key|token|auth|cert|credential',
        re.IGNORECASE
    )

    masked_env = []

    # If dict is passed somehow, convert to list of KEY=VALUE strings
    if isinstance(env_list, dict):
        env_items = [f"{k}={v}" for k, v in env_list.items()]
    else:
        env_items = env_list or []

    for env_str in env_items:
        if "=" in env_str:
            key, val = env_str.split("=", 1)
            if sensitive_keys.search(key):
                masked_env.append(f"{key}=***MASKED***")
            else:
                masked_env.append(env_str)
        else:
            masked_env.append(env_str)

    return masked_env
