# Language Selection, source: https://github.com/bigcode-project/bigcode-dataset/blob/main/language_selection/programming-languages-to-file-extensions.json  # noqa E501
from typing import Dict

from pr_agent.config_loader import get_settings

_language_extension_map = None


def filter_bad_extensions(files):
    # Cache settings and bad extensions to avoid redundant Dynaconf/context lookups.
    settings = get_settings()
    bad_extensions = settings.bad_extensions.default
    if settings.config.use_extra_bad_extensions:
        # Use list concatenation to avoid in-place modification if Dynaconf returns cached list
        bad_extensions = bad_extensions + settings.bad_extensions.extra
    # Precompute set for O(1) lookups on large file lists (if needed)
    bad_ext_set = set(bad_extensions)
    auto_generated_files = ["package-lock.json", "yarn.lock", "composer.lock", "Gemfile.lock", "poetry.lock"]
    auto_generated_check = tuple(auto_generated_files)

    def is_valid_file(filename, bad_ext_set=bad_ext_set):
        if not filename:
            return False
        # Efficient auto-generated-suffix check
        if filename.endswith(auto_generated_check):
            return False
        ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
        return ext not in bad_ext_set

    # List comprehension remains most efficient
    return [f for f in files if f.filename is not None and is_valid_file(f.filename)]


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
    # sort languages by their size
    languages_sorted_list = [k for k, v in sorted(languages.items(), key=lambda item: item[1], reverse=True)]

    # Precomputed global extension map (lowercase keys)
    language_extension_map = _get_language_extension_map()

    main_extensions = []
    for language in languages_sorted_list:
        lang_lc = language.lower()
        main_extensions.append(language_extension_map.get(lang_lc, []))

    # filter out files bad extensions
    files_filtered = filter_bad_extensions(files)

    # Early out if no languages detected
    if not languages:
        return [({"language": "Other", "files": list(files_filtered)})]

    # Flatten main_extensions only once, use set for O(1) lookup
    main_extensions_flat = set()
    for ext_list in main_extensions:
        main_extensions_flat.update(ext_list)

    files_sorted = []
    rest_files = {}
    # Precompute file extensions for rest_files checks
    file_ext_map = {}
    for file in files_filtered:
        ext_str = _get_file_extension(file.filename)
        file_ext_map[file.filename] = ext_str

    # For each language, select files that match its extension list
    used_files = set()
    for extensions, lang in zip(main_extensions, languages_sorted_list):
        extensions_set = set(extensions)
        tmp = []
        for file in files_filtered:
            fname = file.filename
            ext_str = file_ext_map[fname]
            if ext_str in extensions_set:
                tmp.append(file)
                used_files.add(fname)
        if tmp:
            files_sorted.append({"language": lang, "files": tmp})

    # Compute rest_files: those not sorted above and with unknown extension
    for file in files_filtered:
        fname = file.filename
        ext_str = file_ext_map[fname]
        # Only add unsorted files, and those whose extension isn't a known main extension
        if fname not in used_files and ext_str not in main_extensions_flat and fname not in rest_files:
            rest_files[fname] = file

    files_sorted.append({"language": "Other", "files": list(rest_files.values())})
    return files_sorted


def _get_language_extension_map():
    global _language_extension_map
    if _language_extension_map is None:
        # Lazily compute only once, even if get_settings changes.
        language_extension_map_org = get_settings().language_extension_map_org
        _language_extension_map = {k.lower(): v for k, v in language_extension_map_org.items()}
    return _language_extension_map


def _get_file_extension(filename):
    # Returns ".ext" for 'foo.ext' or '' if filename does not contain a '.'
    # This avoids recomputation; kept as a helper for possible future extension/memoization
    idx = filename.rfind(".")
    return f".{filename[idx + 1 :]}" if idx != -1 and idx + 1 < len(filename) else ""
