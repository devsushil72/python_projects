import subprocess
import json
import gzip
import os
import re
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

    packages = {}

    for line in result.stdout.splitlines():
        try:
            name, version, maintainer = line.split("|", 2)

            packages[name] = {
                "name": name,
                "version": version,
                "vendor": maintainer,
                "installation_date": None,
                "path" :None,
                "signed": None,
                "signedBy": None,
                "authority": None,
                "source": "apt"
            }

        except Exception:
            continue

    return packages

INSTALL_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+install\s+([^:]+)"
)


def get_install_dates():
    install_dates = {}

    files = []

    if os.path.exists("/var/log/dpkg.log"):
        files.append("/var/log/dpkg.log")

    for file in os.listdir("/var/log"):
        if file.startswith("dpkg.log."):

            path = f"/var/log/{file}"

            try:
                if path.endswith(".gz"):
                    fp = gzip.open(path, "rt", errors="ignore")
                else:
                    fp = open(path, "r", errors="ignore")

                with fp:
                    for line in fp:
                        m = INSTALL_RE.match(line)

                        if not m:
                            continue

                        ts, pkg = m.groups()

                        if pkg not in install_dates:
                            install_dates[pkg] = ts

            except Exception:
                pass

    return install_dates

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

PATH_PRIORITY = (
    "/opt/",
    "/usr/bin/",
    "/usr/sbin/",
    "/snap/bin/"
)

def get_installation_path(package_name):

    try:
        result = subprocess.run(
            ["dpkg", "-L", package_name],
            capture_output=True,
            text=True,
            timeout=10
        )

        paths = result.stdout.splitlines()

        for prefix in PATH_PRIORITY:
            for path in paths:

                if not path.startswith(prefix):
                    continue

                if os.path.isfile(path) and os.access(path, os.X_OK):
                    return path

        return None

    except Exception:
        return None

def build_inventory():

    packages = get_dpkg_packages()

    install_dates = get_install_dates()
    # Install dates 
    for pkg, ts in install_dates.items():

        if pkg in packages:
            packages[pkg]["installation_date"] = ts
    for pkg in packages:
        packages[pkg]["path"] = get_installation_path(pkg)


    #     trust = get_package_authority(pkg)

    #     packages[pkg].update(trust)

    packages.update(get_snap_packages())

    return list(packages.values())

data = build_inventory()

with open("dpkg_installed_applications.json", "w") as f:
    json.dump(data, f, indent=4)
