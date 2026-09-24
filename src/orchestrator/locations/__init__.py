"""Dagster code locations. Imported by every location before it builds its definitions."""

import warnings

from dagster import BetaWarning, PreviewWarning

# Dagster's own loaders call their own beta and preview APIs (`LocalFileCodeReference` and
# `CodeReferencesMetadataValue` for every defs.yaml, `load_definitions_from_module`) and warn
# about it on every load, dozens of lines with nothing to act on. Ignore those warnings when
# they originate in a Dagster package; a beta API called from this repo still warns.
for _category in (BetaWarning, PreviewWarning):
    warnings.filterwarnings("ignore", category=_category, module=r"dagster(_\w+)?\.")
