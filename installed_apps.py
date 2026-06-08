import subprocess
import logging
import re
import datetime
import subprocess
import os
import re
import logging
import json

TIMEOUT_SUBPROCESS=10
from datetime import datetime
def get_application_patch_info(os_installation_date):

    def extract_real_version(version: str) -> str:
        try:
            version = version.strip()

            # Remove epoch
            if ":" in version:
                version = version.split(":", 1)[1]

            # Remove Debian/Ubuntu revision suffix
            version = re.split(r'[-+~]', version, maxsplit=1)[0]

            return version.strip()

        except Exception:
            return version

    def clean_package_name(name: str) -> str:
        if not name:
            return ""
        name = name.lower().strip()
        name = re.sub(r':\w+$', '', name)  # strip :amd64 arch suffix
        return name
    
    def get_manually_installed_packages() -> set:
        """
        Returns set of package names explicitly installed by user.
        Packages NOT in extended_states are also manual (installed before
        apt started tracking, or via dpkg directly).
        """
        manual = set()
        auto = set()

        ext_states = "/var/lib/apt/extended_states"

        if not os.path.exists(ext_states):
            return manual  # can't determine, return empty → caller treats all as manual

        current_pkg = None
        current_arch = None

        with open(ext_states, "r", errors="ignore") as f:
            for line in f:
                line = line.strip()

                if line.startswith("Package:"):
                    current_pkg = line.split(":", 1)[1].strip()

                elif line.startswith("Architecture:"):
                    current_arch = line.split(":", 1)[1].strip()

                elif line.startswith("Auto-Installed:"):
                    value = line.split(":", 1)[1].strip()
                    if current_pkg:
                        if value == "1":
                            auto.add(current_pkg)
                        else:
                            manual.add(current_pkg)
                    current_pkg = None
                    current_arch = None

        return manual, auto

    def build_path_map() -> dict:
        """
        Read /var/lib/dpkg/info/<pkg>.list files directly — no subprocess.
        Returns {pkg_name: best_path}

        Priority:
            1. Binary in BIN_DIRS          (/usr/bin/, /usr/sbin/, etc.)
            2. Binary in deep LIB_DIRS     (/usr/lib/<pkg>/app — vendor apps like chrome)
            3. Shared library in LIB_DIRS  (.so files)
            4. Executable in OPT_DIRS      (/opt/vendor/app/binary)
        """
        BIN_DIRS = (
            "/usr/bin/", "/usr/sbin/",
            "/bin/", "/sbin/",
            "/usr/local/bin/", "/usr/local/sbin/",
            "/usr/games/",                          # ← game binaries
            "/usr/local/games/",
        )
        LIB_DIRS = (
            "/usr/lib/", "/usr/lib64/",
            "/usr/lib/x86_64-linux-gnu/",           # ← arch-specific lib binaries
            "/usr/lib/aarch64-linux-gnu/",
            "/usr/libexec/",                         # ← libexec binaries
            "/lib/", "/lib64/",
        )
        OPT_DIRS = (
            "/opt/",
        )
        SKIP_PREFIXES = (
            "/usr/share/doc/",
            "/usr/share/man/",
            "/usr/share/locale/",
            "/usr/share/lintian/",
            "/usr/share/bug/",
            "/usr/share/examples/",
            "/usr/share/help/",
            "/usr/share/pixmaps/",
            "/usr/share/icons/",
            "/usr/share/applications/",
            "/usr/share/metainfo/",
            "/usr/share/zsh/",
            "/usr/share/bash-completion/",
            "/usr/share/fish/",
            "/usr/share/perl5/",
            "/usr/share/python3/",
        )
        USELESS = {
            ".", "/", "/.",
            "/usr", "/usr/share", "/usr/lib", "/usr/lib64",
            "/usr/sbin", "/usr/bin", "/bin", "/sbin",
            "/lib", "/lib64",
            "/usr/local", "/usr/local/bin", "/usr/local/sbin",
            "/usr/games", "/usr/local/games",
            "/opt", "/usr/libexec",
        }

        DPKG_INFO_DIR = "/var/lib/dpkg/info"
        path_map = {}

        try:
            for entry in os.scandir(DPKG_INFO_DIR):         # faster than listdir + open
                if not entry.name.endswith(".list"):
                    continue

                pkg_name = entry.name[:-5].split(":")[0]    # strip .list and :amd64
                best_bin = ""
                best_lib_bin = ""                            # deep lib binary e.g. /usr/lib/chrome/chrome
                best_lib = ""                                # .so file
                best_opt = ""

                try:
                    with open(entry.path, "r", errors="ignore") as fh:
                        for line in fh:
                            path = line.strip()

                            if not path or path in USELESS:
                                continue
                            if any(path.startswith(s) for s in SKIP_PREFIXES):
                                continue

                            # Tier 1: standard binary path — best possible, stop reading
                            if any(path.startswith(b) for b in BIN_DIRS):
                                best_bin = path
                                break                        # can't do better

                            # Tier 2: deep lib binary (no extension = likely executable)
                            # e.g. /usr/lib/firefox/firefox, /usr/lib/google-chrome/chrome
                            if not best_lib_bin and any(path.startswith(l) for l in LIB_DIRS):
                                basename = os.path.basename(path)
                                if basename and "." not in basename:  # no extension = executable
                                    best_lib_bin = path
                                    continue

                            # Tier 3: shared library (.so file)
                            if not best_lib and any(path.startswith(l) for l in LIB_DIRS):
                                if ".so" in path:
                                    best_lib = path
                                    continue

                            # Tier 4: /opt executable (must have no extension or known binary ext)
                            if not best_opt and path.startswith("/opt/"):
                                basename = os.path.basename(path)
                                # skip shallow dirs like /opt/google or /opt/google/chrome/
                                if basename and path.count("/") >= 3:
                                    best_opt = path

                except (OSError, PermissionError):
                    pass

                chosen = best_bin or best_lib_bin or best_lib or best_opt
                if chosen:
                    path_map[pkg_name] = chosen

        except Exception as e:
            print("build_path_map error: %s", repr(e))

        return path_map

    def get_install_dates_from_fs() -> dict:
        install_dates = {}
        dpkg_info_dir = "/var/lib/dpkg/info"

        for entry in os.scandir(dpkg_info_dir):
            if not entry.name.endswith(".list"):
                continue

            pkg_name = entry.name[:-5]              # strip ".list"
            if ":" in pkg_name:
                pkg_name = pkg_name.split(":")[0]   # strip ":amd64" etc.

            try:
                st = entry.stat()
                btime = getattr(st, "st_birthtime", None)
                ts = btime if (btime and btime != 0) else st.st_mtime

                install_dates[pkg_name] = datetime.fromtimestamp(ts).strftime(
                    "%d-%m-%Y %H:%M:%S"
                )
            except ValueError as err:
                print(f"Value error for {pkg_name}: {err}")
            except OSError as err:
                print(f"OS error for {pkg_name}: {err}")                
        return install_dates

    def extract_maintainer_org(maintainer: str) -> str:
        if not maintainer:
            return ""
        # Strip Snap verified publisher badge (**)
        maintainer = maintainer.strip().rstrip('*')
        org = maintainer.split("<")[0].strip()
        org = re.sub(
            r',?\s*(Inc\.?|LLC|Ltd\.?|Corporation|Corp\.?|GmbH|s\.r\.o\.?)$',
            '', org, flags=re.IGNORECASE
        ).strip().rstrip(',')
        return org

    def parse_snap_list(output: str) -> list:
        """
        Parse `snap list` output using header column offsets.
        Handles variable-width columns correctly.
        """
        lines = output.strip().split("\n")
        if not lines:
            return []

        # Parse header to get column start positions
        header = lines[0]
        columns = ["Name", "Version", "Rev", "Tracking", "Publisher", "Notes"]
        col_positions = {}

        for col in columns:
            idx = header.find(col)
            if idx != -1:
                col_positions[col] = idx

        snaps = []

        for line in lines[1:]:
            if not line.strip():
                continue
            try:
                def extract_col(col: str) -> str:
                    start = col_positions.get(col, -1)
                    if start == -1:
                        return ""
                    # end = start of next column or end of line
                    next_starts = sorted(
                        pos for c, pos in col_positions.items()
                        if pos > start
                    )
                    end = next_starts[0] if next_starts else len(line)
                    return line[start:end].strip()

                snaps.append({
                    "name":      extract_col("Name"),
                    "version":   extract_col("Version"),
                    "rev":       extract_col("Rev"),
                    "tracking":  extract_col("Tracking"),
                    "publisher": extract_col("Publisher"),
                    "notes":     extract_col("Notes"),
                })
            except Exception:
                continue

        return snaps

# Snap Application Collectors

    def extract_snap_version(version: str) -> str:
        try:
            version = version.strip()

            if not version:
                return "1.0"

            # Strip leading 'v' prefix — v10.16.2 → 10.16.2
            if version.startswith("v") and version[1:2].isdigit():
                version = version[1:]

            # Git hash only (7-12 hex chars) — keep as is: 8761a556
            if re.fullmatch(r'[0-9a-f]{7,12}', version):
                return version

            # Date-based version (8 digits) — keep as is: 20260204
            if re.fullmatch(r'\d{8}', version):
                return version

            # 0+git.xxx-sdk0+git.yyy → take only first part: 0+git.xxx
            if "-sdk" in version:
                version = version.split("-sdk")[0]

            # semver + git suffix → strip git part
            # 3.28.0-19-g98f9e67.98f9e67 → 3.28.0
            # 0.1-81-g442e511            → 0.1
            version = re.sub(r'-\d+-g[0-9a-f]+.*$', '', version)

            # Strip snap revision suffix: 25.0.7-snap211 → 25.0.7
            version = re.sub(r'-snap\d+$', '', version)

            # Strip purely numeric debian revision: 151.0.2-1 → 151.0.2
            version = re.sub(r'-\d+$', '', version)

            return version.strip() or "1.0"

        except Exception:
            return version

    def get_snap_install_dates(snap_entries: list) -> dict:
        """
        Get install date from snap revision directory mtime.
        Birth time is unsupported on squashfs — mtime is reliable here
        since snap revision dirs are root-owned and set by snapd at install time.
        """
        install_dates = {}

        for entry in snap_entries:
            pkg_name = entry["name"]
            rev      = entry["rev"]
            path     = f"/snap/{pkg_name}/{rev}"

            try:
                st = os.stat(path)
                ts = st.st_mtime      # ✅ mtime is correct for squashfs snap mounts

                install_dates[pkg_name] = datetime.fromtimestamp(ts).strftime(
                    "%d-%m-%Y %H:%M:%S"
                )

            except ValueError as  err:
                print(f"error fetching snap installation date : {err}")

        return install_dates
    
    def is_git_hash(version: str) -> bool:
        """Detect pure git hash versions like 8761a556"""
        return bool(re.fullmatch(r'[0-9a-f]{7,12}', version.strip()))


    def get_version_from_binary(pkg_name: str) -> str:
        real_user = os.environ.get("SUDO_USER")
        SPECIAL_COMMANDS = {
            # VS Code family
            "code": ["code", "--version"],
            "code-insiders": ["code-insiders", "--version"],

            # Snap tools
            "canonical-livepatch": ["canonical-livepatch", "version"],
            "snapd": ["snap", "version"],

            # Browsers
            "chromium": ["chromium", "--version"],
            "google-chrome": ["google-chrome", "--version"],

            # Docker
            "docker": ["docker", "--version"],
        }

        VERSION_FLAGS = [
            ["--version"],
            ["-v"],
            ["version"],
            ["-version"],
        ]

        if pkg_name in SPECIAL_COMMANDS:
            cmds = [SPECIAL_COMMANDS[pkg_name]]
        else:
            cmds = [[pkg_name] + flag for flag in VERSION_FLAGS]

        for cmd in cmds:
            try:
                final_cmd = cmd

                # Run GUI apps as original user instead of root
                if (
                    real_user
                    and pkg_name in {
                        "code",
                        "code-insiders",
                        "chromium",
                        "google-chrome",
                    }
                ):
                    final_cmd = ["sudo", "-u", real_user] + cmd

                print(f"trying command: {final_cmd}")

                result = subprocess.run(
                    final_cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                output = result.stdout or result.stderr

                print(f"output: {output}")

                for line in output.splitlines():
                    m = re.search(r'(\d+\.\d+(?:\.\d+)*)', line.strip())
                    if m:
                        return m.group(1)

            except Exception as e:
                print(f"failed command {final_cmd}: {e}")

        return ""

    def is_unresolvable_snap(pkg_name: str) -> bool:
        """
        Detect system/runtime snaps that have no binary
        and no meaningful version — return 1.0 for these.
        """
        EXACT = {
            "bare",
            "snap-store",
            "firmware-updater",
            "snapd-desktop-integration",
        }
        PREFIXES = (
            "core",         # core, core18, core20, core22, core24, core26 ...
            "gnome-",       # gnome-42-2204, gnome-46-2404 ...
            "gtk-common-",  # gtk-common-themes
            "mesa-",        # mesa-2404
            "kde-",         # kde frameworks
        )

        return pkg_name in EXACT or any(pkg_name.startswith(p) for p in PREFIXES)


    def resolve_snap_version(pkg_name: str, raw_version: str) -> str:
        """
        Resolve real version for a snap package.

        Priority:
            1. Unresolvable snap (runtime/base)  → "1.0"
            2. Known binary command              → real upstream version
            3. Clean extract                     → stripped version string
            4. Fallback                          → "1.0"
        """
        # Step 1: system/runtime snaps — no meaningful version exists
        if is_unresolvable_snap(pkg_name):
            return "1.0"

        # Step 2: git hash or empty — try binary
        if is_git_hash(raw_version) or not raw_version.strip():
            binary_version = get_version_from_binary(pkg_name)
            if binary_version:
                return binary_version

        # Step 3: clean whatever snap list gave us
        return extract_snap_version(raw_version) or "1.0"
    
    def has_numeric_version(version: str) -> bool:
        """
        Returns True only for semantic/numeric versions.
        Examples:
            1.0
            1.2.3
            10.16.2
            151.0.2-1
        """
        if not version:
            return False

        return bool(
            re.search(r'\d+\.\d+', version)
        )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Main logic
    # ─────────────────────────────────────────────────────────────────────────
    applications_versions = []
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 1: Parse dpkg-query to get package list (same as before)
    # ─────────────────────────────────────────────────────────────────────────
    raw_packages =  []  # list of (pkg_name, version, maintainer)
    try:
        result = subprocess.run(
            "dpkg-query -W -f='${Package}|${Version}|${Maintainer}\\n'",
            shell=True, capture_output=True, text=True,
            timeout=TIMEOUT_SUBPROCESS
        )
        if result.returncode != 0:
            logging.error("dpkg-query failed: %s", result.stderr)
        else:
            for line in result.stdout.strip().split("\n"):
                try:
                    pkg_name, version, maintainer = line.strip().split("|", 2)
                    raw_packages.append((pkg_name, version, maintainer))
                except Exception as e:
                    logging.warning("APT parse error for line %s: %s", line, e)

    except subprocess.TimeoutExpired:
        logging.error("dpkg-query timed out")
    except Exception as e:
        logging.error("APT fetch error: %s", repr(e))

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 2: ONE batch call to get all binary paths (replaces 1,760 subprocs)
    # ─────────────────────────────────────────────────────────────────────────
    path_map = build_path_map()
    path_map["cyberauditor-linux-agent"] = "/etc/cyberauditor_linux_agent"
    package_installation_date = get_install_dates_from_fs()
    # print(len(package_installation_date))
    manual, auto = get_manually_installed_packages()
    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: Process each package — now pure Python, no subprocesses
    # ─────────────────────────────────────────────────────────────────────────
    for pkg_name, version, maintainer in raw_packages:
        try:
            if pkg_name in auto and pkg_name not in manual:
                continue
            version_clean = extract_real_version(version)
            path = path_map.get(pkg_name) or path_map.get(pkg_name.lower(), "")  # O(1) dict lookup
            date=package_installation_date.get(pkg_name) 

            signed = True
            signed_by = extract_maintainer_org(maintainer)
            authority = "Ubuntu APT Repository"
            clean_name = clean_package_name(pkg_name)
            # normalized_name = FAMILY_NAME_OVERRIDE.get(clean_name, clean_name)
            # lookup = normalized_name.lower()
            # if lookup in DISPLAY_NAME_OVERRIDE:
            #     normalized_name = DISPLAY_NAME_OVERRIDE[lookup]

            # lookup = normalized_name.lower()
            vendor = extract_maintainer_org(maintainer)
            # if lookup in VENDOR_OVERRIDE:
            #     vendor = VENDOR_OVERRIDE[lookup]

            app_obj = {
                "name": pkg_name,
                # "version": version_clean,
                # "vendor": vendor,
                # "date": date if date else os_installation_date,
                "path": path if path else "Not Found",
                # "signed": signed,
                # "signedBy": signed_by,
                # "authority": authority,
            }
            applications_versions.append(app_obj)

        except Exception as e:
            logging.warning("APT process error for %s: %s", pkg_name, e)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: Snap packages — unchanged, but use fallback path helper
    # ─────────────────────────────────────────────────────────────────────────
    try:
        EXCLUDED_SNAPS = {
            "bare",
            "core18",
            "core20",
            "core22",
            "core24",
            "gnome-3-28-1804",
            "gnome-3-38-2004",
            "gnome-42-2204",
            "gnome-46-2404",
            "gtk-common-themes",
            "mesa-2404",
            "desktop-security-center"
        }
        
        snap_result = subprocess.run(
            ["snap", "list"],
            capture_output=True, text=True,
            timeout=TIMEOUT_SUBPROCESS
        )
        
        if snap_result.returncode == 0:
            snap_entries = parse_snap_list(snap_result.stdout)
            snap_dates    = get_snap_install_dates(snap_entries)
            for entry in snap_entries:
                try:
                    
                    pkg_name  = entry["name"]
                    if pkg_name in EXCLUDED_SNAPS:
                        continue
                    version  = resolve_snap_version(pkg_name, entry["version"])
                    if not has_numeric_version(version):
                        continue
                    publisher = entry["publisher"] or "Snap Store"
                    # rest of your existing logic unchanged
                    path      = f"/snap/{pkg_name}/current"
                    signed    = True
                    signed_by = extract_maintainer_org(publisher)
                    authority = "Snap Store"
                    
                    date= snap_dates.get(pkg_name)
                    clean_name      = clean_package_name(pkg_name)
                    # normalized_name = FAMILY_NAME_OVERRIDE.get(clean_name, clean_name)
                    # lookup          = normalized_name.lower()

                    # if lookup in DISPLAY_NAME_OVERRIDE:
                    #     normalized_name = DISPLAY_NAME_OVERRIDE[lookup]

                    # lookup = normalized_name.lower()
                    vendor = extract_maintainer_org(publisher)
                    # if lookup in VENDOR_OVERRIDE:
                    #     vendor = VENDOR_OVERRIDE[lookup]

                    app_obj = {
                        "name":      clean_name,
                        "version":   version if version else "1.0",
                        "vendor":    vendor,
                        "date":      date if date else os_installation_date,
                        "path":      path,
                        "signed":    signed,
                        "signedBy":  signed_by,
                        "authority": authority,
                    }
                    applications_versions.append(app_obj)

                except Exception as e:
                    logging.warning("Snap parse error for %s: %s", entry, e)

    except FileNotFoundError:
        logging.info("snap not installed — skipping")
    except Exception as e:
        logging.error("Snap fetch error: %s", repr(e))

    return applications_versions

data = get_application_patch_info(datetime.now().strftime("%Y-%m-%d"))
with open("installed_applications.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("JSON saved to installed_applications.json")
