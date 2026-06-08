from jinja2 import filters
import subprocess
import json
import gzip
import os
import re
import datetime

TIMEOUT_SUBPROCESS=10
def get_dpkg_packages():
    result = subprocess.run(
        [
            "dpkg-query",
            "-W",
            "-f=${Package}|${Version}|${Maintainer}\n"
        ],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SUBPROCESS
    )

    manual, auto = get_manually_installed_packages()

    packages = {}

    for line in result.stdout.splitlines():
        try:
            name, version, maintainer = line.split("|", 2)
            if name in auto and name not in manual:
                continue
            packages[name] = {
                "name": name,
                "version": version,
                "vendor": maintainer,
                "installation_date": None,
                "path" :"",
                "signed": "",
                "signedBy": "",
                "authority": "",
                "source": "apt"
            }

        except Exception:
            continue

    return packages

ORIGIN_RE = re.compile(r"o=([^,]+)")

def get_package_authority(pkg):

    try:
        result = subprocess.run(
            ["apt-cache", "policy", pkg],
            capture_output=True,
            text=True,
            timeout=10
        )

        origin = None

        for line in result.stdout.splitlines():

            m = ORIGIN_RE.search(line)

            if m:
                origin = m.group(1)
                break

        return {
            "signed": origin is not None,
            "signedBy": origin,
            "authority": origin
        }

    except Exception:
        return {
            "signed": False,
            "signedBy": None,
            "authority": None
        }

def get_snap_packages():

    try:
        result = subprocess.run(
            ["snap", "list"],
            capture_output=True,
            text=True,
            timeout=30
        )

        packages = {}

        lines = result.stdout.splitlines()[1:]

        for line in lines:

            cols = line.split()

            if len(cols) < 2:
                continue

            name = cols[0]
            version = cols[1]

            packages[name] = {
                "name": name,
                "version": version,
                "vendor": "Snap",
                "installation_date": None,
                "signed": True,
                "signedBy": "Snap Store",
                "authority": "Canonical",
                "source": "snap"
            }

        return packages

    except Exception:
        return {}


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
    )
    LIB_DIRS = (
        "/usr/lib/", "/usr/lib64/",
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
    )
    USELESS = {
        ".", "/", "/.",
        "/usr", "/usr/share", "/usr/lib", "/usr/lib64",
        "/usr/sbin", "/usr/bin", "/bin", "/sbin",
        "/lib", "/lib64",
        "/usr/local", "/usr/local/bin", "/usr/local/sbin",
        "/opt",
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

            install_dates[pkg_name] = datetime.datetime.fromtimestamp(ts).strftime(
                "%d-%m-%Y %H:%M:%S"
            )
        except Exception:
            continue

    return install_dates


def build_inventory():

    packages = get_dpkg_packages()

    install_dates = get_install_dates_from_fs()
    manual, auto  = get_manually_installed_packages()
    for pkg, ts in install_dates.items():

        if pkg in packages:
            packages[pkg]["installation_date"] = ts

    packages.update(get_snap_packages())

    path_map = build_path_map()
    for pkg, path in path_map.items():
        if pkg in packages:
            packages[pkg]["path"] = path


    return list(packages.values())

data = build_inventory()

with open("dpkg_installed_applications.json", "w") as f:
    json.dump(data, f, indent=4)
