# Language Selection, source: https://github.com/bigcode-project/bigcode-dataset/blob/main/language_selection/programming-languages-to-file-extensions.json  # noqa E501
from typing import Dict

from pr_agent.config_loader import get_settings

_BAD_EXTENSIONS_CACHE = {}

_LANGUAGE_EXTENSION_MAP_CACHE = {}


def filter_bad_extensions(files):
    # Use static cache for bad extensions and minimize settings access per batch
    settings = get_settings()
    bad_ext_key = (
        id(settings.bad_extensions.default),
        id(settings.bad_extensions.extra),
        getattr(settings.config, "use_extra_bad_extensions", False),
    )
    global _BAD_EXTENSIONS_CACHE
    if bad_ext_key not in _BAD_EXTENSIONS_CACHE:
        merged = list(settings.bad_extensions.default)
        if getattr(settings.config, "use_extra_bad_extensions", False):
            merged += settings.bad_extensions.extra
        _BAD_EXTENSIONS_CACHE[bad_ext_key] = set(merged)
    bad_extensions_set = _BAD_EXTENSIONS_CACHE[bad_ext_key]
    return [f for f in files if f.filename is not None and is_valid_file(f.filename, bad_extensions_set)]


def is_valid_file(filename: str, bad_extensions=None) -> bool:
    if not filename:
        return False
    if not bad_extensions:
        bad_extensions = get_settings().bad_extensions.default
        if get_settings().config.use_extra_bad_extensions:
            bad_extensions += get_settings().bad_extensions.extra

    auto_generated_files = ["package-lock.json", "yarn.lock", "composer.lock", "Gemfile.lock", "poetry.lock"]
    for forbidden_file in auto_generated_files:
        if filename.endswith(forbidden_file):
            return False

    return filename.split(".")[-1] not in bad_extensions


def sort_files_by_main_languages(languages: Dict, files: list):
    """
    Sort files by their main language, put the files that are in the main language first and the rest files after
    """
    # Sort languages by their size
    languages_sorted_list = [k for k, v in sorted(languages.items(), key=lambda item: item[1], reverse=True)]

    # Use cache for language extension mapping, expensive if recomputed often
    settings = get_settings()
    language_extension_map_org = settings.language_extension_map_org
    lang_map_id = id(language_extension_map_org)
    global _LANGUAGE_EXTENSION_MAP_CACHE
    if lang_map_id not in _LANGUAGE_EXTENSION_MAP_CACHE:
        # Lowercase keys once and cache
        _LANGUAGE_EXTENSION_MAP_CACHE.clear()  # Keeps only most-recent; avoids memory leaks if settings change
        _LANGUAGE_EXTENSION_MAP_CACHE[lang_map_id] = {k.lower(): v for k, v in language_extension_map_org.items()}
    language_extension_map = _LANGUAGE_EXTENSION_MAP_CACHE[lang_map_id]

    main_extensions = []
    for language in languages_sorted_list:
        lang_lc = language.lower()
        if lang_lc in language_extension_map:
            main_extensions.append(language_extension_map[lang_lc])
        else:
            main_extensions.append([])

    files_filtered = filter_bad_extensions(files)

    files_sorted = []
    rest_files = {}

    if not languages:
        files_sorted = [({"language": "Other", "files": list(files_filtered)})]
        return files_sorted

    # Flatten main_extensions
    main_extensions_flat = [item for sublist in main_extensions for item in sublist]
    # Convert to set for O(1) extension membership check in "Other" logic
    main_extensions_flat_set = set(main_extensions_flat)

    # Precompute extensions for all files just once to avoid splitting repeatedly in nested loops
    file_ext_map = {}
    for file in files_filtered:
        # Only split from last '.', avoid new string construction
        ext = "." + file.filename.rpartition(".")[-1] if "." in file.filename else ""
        file_ext_map[file.filename] = ext

    # For each language/main extension group, partition files efficiently
    for extensions, lang in zip(main_extensions, languages_sorted_list):
        # Use set for O(1) lookup
        extensions_set = set(extensions)
        tmp = []
        for file in files_filtered:
            extension_str = file_ext_map[file.filename]
            if extension_str in extensions_set:
                tmp.append(file)
            else:
                if file.filename not in rest_files and extension_str not in main_extensions_flat_set:
                    rest_files[file.filename] = file
        if len(tmp) > 0:
            files_sorted.append({"language": lang, "files": tmp})
    files_sorted.append({"language": "Other", "files": list(rest_files.values())})
    return files_sorted
