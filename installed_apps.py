import subprocess
import logging
import re
import configparser
from datetime import datetime,date
import subprocess
import os
import re
import logging
import json
import glob

TIMEOUT_SUBPROCESS=10
from datetime import datetime
def get_application_patch_info(os_installation_date):

    _SKIP_PATTERNS_RAW = [
        r'^adwaita-', r'-icon-theme$', r'^fonts-', r'^ttf-', r'^xfonts-',
        r'font$', r'fonts$', r'^language-pack', r'^locales', r'-doc$',
        r'-docs$', r'^core\d+$', r'^bare$', r'^gnome-\d+-\d+$',
        r'^gtk-common-themes$', r'-dev$', r'^wallpapers-', r'-wallpapers$',
        r'^gnome-backgrounds', r'^yaru', r'^sound-theme',
        r'^lib.*-dev$', r'^.*-dbgsym$', r'^.*-dbg$', r'^python3-gdb$',
        r'^hunspell-', r'^aspell-', r'^mythes-', r'^wamerican', r'^wbritish',
        r'^wallpapers-', r'-wallpapers$', r'^gnome-backgrounds', r'^yaru',
        r'^sound-theme', r'^linux-headers', r'^linux-tools', r'^linux-modules',
        r'^linux-image', r'^linux-firmware', r'^linux-generic', r'^linux-base$',
        r'^gir1\.', r'^glib-networking', r'^gtk-update-icon-cache$',
        r'^shared-mime-info$', r'^xdg-', r'^iso-codes$',
        r'-common$', r'-data$', r'-locale$', r'-l10n$', r'-translations$',
        r'^gnome-\d', r'^mesa-', r'^snap-store$', r'^snapd-desktop-integration$',
        r'-plugin-', r'-keyring$',
        r'^libreoffice-(base|calc|core|draw|gnome|gtk3|impress|math|writer).*',
        r'^libreoffice-script-provider-.*', r'^libreoffice-sdbc-.*',
        r'^libreoffice-style-.*', r'^libreoffice-uiconfig-.*',
        r'^libreoffice-nlpsolver$', r'^libreoffice-wiki-publisher$',
        r'^libreoffice-report-builder$', r'^libreoffice-report-builder-bin$',
        r'^python-babel-localedata$', r'^python3-.*',
        r'^qemu-block-extra$', r'^qemu-system-gui$',
        r'^qemu-system-modules-opengl$', r'^qemu-system-modules-spice$',
        r'^libvirt-daemon-.*',
        r'^cpp-\d+-x86-64-linux-gnu$', r'^cpp-x86-64-linux-gnu$',
        r'^g\+\+-\d+-x86-64-linux-gnu$', r'^gcc-\d+-base$',
        r'^gcc-\d+-x86-64-linux-gnu$',
        r'^node-', r'^krb5-locales$', r'^aspell$', r'^hunspell-',
        r'^language-selector-', r'^lib.*java$', r'^ure-java$',
        r'^gnome-session-', r'^gnome-shell-extension-',
        r'^gnome-browser-connector$', r'^gnome-bluetooth-sendto$',
        r'^gnome-menus$', r'^printer-driver-', r'^pipewire-(bin|pulse)$',
        r'^aptdaemon$', r'^dh-', r'^debhelper$', r'^fakeroot$', r'^po-debconf$',
        r'^man-db$', r'^install-info$', r'^info$', r'^groff-base$',
        r'^xml-core$', r'^sgml-base$',
        r'^shim-signed$', r'^grub-efi-amd64-(bin|signed|unsigned)$',
        r'^grub-pc-bin$', r'^policykit-', r'^polkitd$',
        r'^systemd-(container|cryptsetup|hwe-hwdb|sysv)$',
        r'^libnss-systemd$', r'^libpam-', r'^ubuntu-helper-virt-hwe$',
        r'^ubuntu-report$', r'^whoopsie', r'^apport$',
        r'^x11-', r'^xserver-xorg-input-', r'^xserver-xorg-video-',
        r'^openjdk-.*-jre-headless$',
        r'^autopoint$', r'^gyp$', r'^licensecheck$', r'^debugedit$',
        r'^dwz$', r'^diffstat$',
        r'^python3\.\d+-tk$',
        r'^python3\.\d+-venv$',
        r'^python3\.\d+-gdbm$',
    ]

    # Single compiled alternation — one re.search() instead of 60+
    _SKIP_REGEX = re.compile("|".join(_SKIP_PATTERNS_RAW), re.IGNORECASE)

    _LANG_ECOSYSTEM_LIB_REGEX = re.compile(
        r'^lib.+-(perl|python\d*|ruby|php)$',
        re.IGNORECASE
    )

    _GENERIC_LIB_REGEX = re.compile(
        r'^(lib|compat-)',
        re.IGNORECASE
    )

    _BASE_SYSTEM_REGEX = re.compile(
        r'^(kernel|filesystem|setup|basesystem|tzdata)',
        re.IGNORECASE
    )

    _DEBUG_DEV_REGEX = re.compile(
        r'(-devel|-debuginfo|-debugsource|-dbg|-dev)$',
        re.IGNORECASE
    )

    _LOCALE_REGEX = re.compile(
        r'(-locale|-lang|-i18n|-l10n|-translations)$',
        re.IGNORECASE
    )

    _LANGUAGE_SUBPACKAGE_REGEX = re.compile(
        r'^(node-|python3?-|perl-|rubygem-|php-|cargo-|go-)',
        re.IGNORECASE
    )

    FAMILY_NAME_OVERRIDE = {
        # =========================
        # Browsers
        # =========================
        "google-chrome-stable": "chrome",
        "google-chrome-beta": "chrome",
        "google-chrome-unstable": "chrome",
        "chromium": "chrome",
        "chromium-browser": "chrome",

        "brave-browser": "brave browser",
        "firefox": "firefox",

        # =========================
        # Editors / IDEs / Dev Tools
        # =========================
        "vim": "vim",
        "vim-tiny": "vim",
        "vim-gtk3": "vim",

        "nano": "nano",
        "gedit": "gedit",

        "code": "visual studio code",

        "git": "git",

        "gdb": "gdb",

        "autoconf": "autoconf",
        "automake": "automake",
        "make": "make",

        # =========================
        # GCC Toolchain
        # =========================
        "gcc": "gcc",
        "gcc-13": "gcc",
        "gcc-14": "gcc",
        "gcc-15": "gcc",

        "gcc-x86-64-linux-gnu": "gcc",
        "gcc-13-x86-64-linux-gnu": "gcc",
        "gcc-14-x86-64-linux-gnu": "gcc",
        "gcc-15-x86-64-linux-gnu": "gcc",

        "cpp": "gcc",
        "cpp-13": "gcc",
        "cpp-14": "gcc",
        "cpp-15": "gcc",

        "g++": "gcc",
        "g++-13": "gcc",
        "g++-14": "gcc",
        "g++-15": "gcc",

        # =========================
        # Programming Languages
        # =========================
        "python3": "python",
        "python3.12": "python",
        "python3.12-minimal": "python",
        "python3.13": "python",
        "python3.13-minimal": "python",
        "python3.14-minimal": "python",

        "libpython3.12": "python",
        "libpython3.12t64": "python",
        "libpython3.12-stdlib": "python",
        "libpython3.12-minimal": "python",

        "perl": "perl",
        "perl-base": "perl",

        "nodejs": "nodejs",

        "openjdk-21-jdk": "openjdk",
        "openjdk-21-jdk-headless": "openjdk",
        "openjdk-21-jre": "openjdk",
        "openjdk-21-jre-headless": "openjdk",

        # =========================
        # Python Libraries
        # =========================
        "python3-cryptography": "cryptography",
        "python3-jwt": "pyjwt",
        "python3-requests": "requests",
        "python3-paramiko": "paramiko",
        "python3-pil": "pillow",
        "python3-yaml": "pyyaml",
        "python3-jinja2": "jinja2",
        "python3-markupsafe": "markupsafe",
        "python3-urllib3": "urllib3",
        "python3-setuptools": "setuptools",
        "python3-pip": "pip",
        "python3-aiohttp": "aiohttp",
        "python3-bcrypt": "bcrypt",
        "python3-pycryptodome": "pycryptodome",
        "python3-oauthlib": "oauthlib",

        # =========================
        # Security / Crypto
        # =========================
        "openssl": "openssl",
        "libssl3": "openssl",
        "libssl3t64": "openssl",
        "libssl-dev": "openssl",

        "sudo": "sudo",

        "apparmor": "apparmor",
        "libapparmor1": "apparmor",

        "gnupg": "gnupg",
        "gpg": "gnupg",
        "gpg-agent": "gnupg",
        "gpgv": "gnupg",

        "auditd": "audit",

        # =========================
        # Networking
        # =========================
        "curl": "curl",
        "libcurl4t64": "curl",
        "libcurl3t64-gnutls": "curl",
        "libcurl4-openssl-dev": "curl",

        "wget": "wget",

        "openssh-client": "openssh",
        "openssh-server": "openssh",
        "openssh-sftp-server": "openssh",

        "bind9": "bind",
        "bind9-dnsutils": "bind",
        "bind9-host": "bind",
        "bind9-libs": "bind",

        "rsync": "rsync",
        "rsyslog": "rsyslog",

        "tcpdump": "tcpdump",
        "nmap": "nmap",

        "openvpn": "openvpn",

        "wpasupplicant": "wpa supplicant",

        "avahi-daemon": "avahi",

        "dnsmasq": "dnsmasq",
        "dnsmasq-base": "dnsmasq",

        # =========================
        # Docker / Containers
        # =========================
        "docker.io": "docker",
        "docker-ce": "docker",
        "docker-ce-cli": "docker",
        "docker-buildx-plugin": "docker",
        "docker-compose": "docker",
        "docker-compose-plugin": "docker",
        "docker-engine": "docker",

        "containerd": "containerd",

        # =========================
        # Virtualization / Remote
        # =========================
        "virtualbox": "virtualbox",
        "virtualbox-7.2": "virtualbox",

        "virtualbox-guest-utils": "virtualbox guest additions",
        "virtualbox-guest-x11": "virtualbox guest additions",
        "virtualbox-guest-dkms": "virtualbox guest additions",

        "remmina": "remmina",

        # =========================
        # Printing
        # =========================
        "cups": "cups",
        "cups-daemon": "cups",
        "cups-client": "cups",
        "cups-browsed": "cups",
        "cups-bsd": "cups",
        "cups-ipp-utils": "cups",
        "cups-ppdc": "cups",

        "cups-filters": "cups filters",
        "cups-filters-core-drivers": "cups filters",

        # =========================
        # GNOME Applications
        # =========================
        "gnome-calculator": "calculator",
        "gnome-clocks": "clocks",
        "gnome-calendar": "calendar",
        "gnome-system-monitor": "system monitor",
        "gnome-terminal": "terminal",
        "nautilus": "files",

        "eog": "image viewer",

        # =========================
        # System / Core Utilities
        # =========================
        "systemd": "systemd",
        "systemd-resolved": "systemd",
        "systemd-timesyncd": "systemd",
        "systemd-oomd": "systemd",

        "snapd": "snapd",

        "dbus": "dbus",
        "dbus-daemon": "dbus",

        "bash": "bash",

        "tar": "tar",
        "grep": "grep",
        "sed": "sed",
        "gawk": "gawk",

        "coreutils": "coreutils",
        "binutils": "binutils",

        "gzip": "gzip",

        "readline-common": "readline",
        "libreadline8t64": "readline",

        "screen": "screen",

        "strace": "strace",

        "dmidecode": "dmidecode",

        "debugedit": "debugedit",

        "iucode-tool": "iucode-tool",

        "pcmciautils": "pcmciautils",

        # =========================
        # Compression
        # =========================
        "bzip2": "bzip2",
        "libbz2-1.0": "bzip2",

        "xz": "xz",
        "xz-utils": "xz",
        "liblzma5": "xz",

        "zlib1g": "zlib",

        "zip": "zip",
        "unzip": "unzip",

        "7zip": "7-zip",
        "p7zip": "7-zip",
        "p7zip-full": "7-zip",

        # =========================
        # Multimedia / Libraries
        # =========================
        "ghostscript": "ghostscript",
        "libgs-common": "ghostscript",

        "ffmpeg": "ffmpeg",
        "libavcodec60": "ffmpeg",

        "imagemagick": "imagemagick",

        "libwebkit2gtk-4.1-0": "webkitgtk",
        "libjavascriptcoregtk-4.1-0": "webkitgtk",
        "libjavascriptcoregtk-6.0-1": "webkitgtk",

        "sqlite3": "sqlite",
        "libsqlite3-0": "sqlite",

        "libssh-4": "libssh",

        # =========================
        # Misc
        # =========================
        "bluez": "bluez",

        "fwupd": "fwupd",

        "mc": "midnight commander",

        "slack": "slack",

        "canonical-livepatch": "canonical livepatch",

        "firmware-updater": "firmware updater",

        "insomnia": "insomnia",
    }

    DISPLAY_NAME_OVERRIDE = {
        "aiohttp": "aiohttp",
        "apparmor": "AppArmor",
        "audit": "Linux Audit",
        "autoconf": "GNU Autoconf",
        "automake": "GNU Automake",
        "avahi": "Avahi",
        "bash": "GNU Bash",
        "bcrypt": "bcrypt",
        "bind": "BIND",
        "binutils": "GNU Binutils",
        "bluez": "BlueZ",
        "brave browser": "Brave Browser",
        "bzip2": "bzip2",
        "calendar": "Calendar",
        "canonical livepatch": "Canonical Livepatch",
        "chrome": "Chrome",
        "clocks": "Clocks",
        "containerd": "containerd",
        "coreutils": "GNU Coreutils",
        "cryptography": "Python Cryptography",
        "cups": "CUPS",
        "cups filters": "CUPS Filters",
        "curl": "curl",
        "dbus": "D-Bus",
        "debugedit": "debugedit",
        "dmidecode": "dmidecode",
        "dnsmasq": "dnsmasq",
        "docker": "Docker",
        "eog": "Image Viewer",
        "ffmpeg": "FFmpeg",
        "files": "Files",
        "firefox": "Firefox",
        "firmware updater": "Firmware Updater",
        "fwupd": "fwupd",
        "gawk": "GNU awk",
        "gcc": "GCC",
        "gdb": "GDB",
        "gedit": "gedit",
        "git": "Git",
        "gmp": "GMP",
        "gnupg": "GnuPG",
        "gnutls": "GnuTLS",
        "ghostscript": "Ghostscript",
        "grep": "GNU grep",
        "gzip": "GNU gzip",
        "imagemagick": "ImageMagick",
        "image viewer": "Image Viewer",
        "insomnia": "Insomnia",
        "iucode-tool": "iucode-tool",
        "jinja2": "Jinja2",
        "libssh": "libssh",
        "make": "GNU Make",
        "markupsafe": "MarkupSafe",
        "midnight commander": "Midnight Commander",
        "nano": "GNU nano",
        "nmap": "Nmap",
        "nodejs": "Node.js",
        "oauthlib": "OAuthLib",
        "openjdk": "OpenJDK",
        "openssh": "OpenSSH",
        "openssl": "OpenSSL",
        "openvpn": "OpenVPN",
        "paramiko": "Paramiko",
        "pcmciautils": "pcmciautils",
        "perl": "Perl",
        "pip": "pip",
        "pillow": "Pillow",
        "pycryptodome": "PyCryptodome",
        "pyjwt": "PyJWT",
        "python": "Python",
        "pyyaml": "PyYAML",
        "readline": "GNU Readline",
        "remmina": "Remmina",
        "requests": "Requests",
        "rsync": "rsync",
        "rsyslog": "rsyslog",
        "screen": "GNU Screen",
        "sed": "GNU sed",
        "setuptools": "setuptools",
        "slack": "Slack",
        "snapd": "snapd",
        "sqlite": "SQLite",
        "strace": "strace",
        "sudo": "sudo",
        "system monitor": "System Monitor",
        "systemd": "systemd",
        "tar": "GNU tar",
        "tcpdump": "tcpdump",
        "terminal": "Terminal",
        "urllib3": "urllib3",
        "vim": "Vim",
        "virtualbox": "VirtualBox",
        "virtualbox guest additions": "VirtualBox Guest Additions",
        "visual studio code": "Visual Studio Code",
        "webkitgtk": "WebKitGTK",
        "wget": "wget",
        "wpa supplicant": "wpa_supplicant",
        "xz": "XZ Utils",
        "zlib": "zlib",
        "zip": "zip",
        "7-zip": "7-Zip",
        "evince": "Evince"
    }

    VENDOR_OVERRIDE = {
        "aiohttp": "aiohttp",
        "apparmor": "Canonical",
        "audit": "Red Hat",
        "autoconf": "GNU",
        "automake": "GNU",
        "avahi": "Avahi",
        "bash": "GNU",
        "bcrypt": "bcrypt",
        "bind": "ISC",
        "binutils": "GNU",
        "bluez": "BlueZ",
        "brave browser": "Brave Software",
        "bzip2": "bzip2",
        "canonical livepatch": "Canonical",
        "chrome": "Google",
        "containerd": "Cloud Native Computing Foundation",
        "coreutils": "GNU",
        "cryptography": "Python Cryptography Authority",
        "cups": "OpenPrinting",
        "cups filters": "OpenPrinting",
        "curl": "curl",
        "dbus": "freedesktop.org",
        "debugedit": "Fedora Project",
        "dmidecode": "Nicolas J. A. Bouliane",
        "dnsmasq": "Simon Kelley",
        "docker": "Docker Inc.",
        "ffmpeg": "FFmpeg",
        "firefox": "Mozilla",
        "firmware updater": "Canonical",
        "fwupd": "fwupd",
        "gawk": "GNU",
        "gcc": "GNU",
        "gdb": "GNU",
        "gedit": "GNOME",
        "git": "Git",
        "gnupg": "GnuPG",
        "gnutls": "GNU",
        "ghostscript": "Artifex",
        "grep": "GNU",
        "gzip": "GNU",
        "imagemagick": "ImageMagick",
        "insomnia": "Kong",
        "iucode-tool": "Intel",
        "jinja2": "Pallets",
        "libssh": "libssh",
        "make": "GNU",
        "markupsafe": "Pallets",
        "midnight commander": "Midnight Commander",
        "nano": "GNU",
        "nmap": "Nmap",
        "nodejs": "OpenJS Foundation",
        "oauthlib": "OAuthLib",
        "openjdk": "OpenJDK",
        "openssh": "OpenBSD",
        "openssl": "OpenSSL",
        "openvpn": "OpenVPN",
        "paramiko": "Paramiko",
        "pcmciautils": "Debian",
        "perl": "Perl",
        "pip": "PyPA",
        "pillow": "Python Pillow",
        "pycryptodome": "Legrandin",
        "pyjwt": "Jose Padilla",
        "python": "Python Software Foundation",
        "pyyaml": "PyYAML",
        "readline": "GNU",
        "remmina": "Remmina",
        "requests": "Python Requests",
        "rsync": "rsync",
        "rsyslog": "Rainer Gerhards",
        "screen": "GNU",
        "sed": "GNU",
        "setuptools": "PyPA",
        "slack": "Slack Technologies",
        "snapd": "Canonical",
        "sqlite": "SQLite",
        "strace": "strace",
        "sudo": "Todd C. Miller",
        "systemd": "systemd",
        "tar": "GNU",
        "tcpdump": "tcpdump",
        "urllib3": "urllib3",
        "vim": "Vim",
        "virtualbox": "Oracle",
        "virtualbox guest additions": "Oracle",
        "visual studio code": "Microsoft",
        "webkitgtk": "WebKitGTK",
        "wget": "GNU",
        "wpa supplicant": "w1.fi",
        "xz": "Tukaani",
        "zlib": "zlib",
        "zip": "Info-ZIP",
        "7-zip": "7-Zip",
    }

    def should_skip(pkg_name: str) -> bool:
        # CRITICAL: packages explicitly in FAMILY_NAME_OVERRIDE are always allowed
        if pkg_name.lower() in FAMILY_NAME_OVERRIDE:
            return False
        return bool(_SKIP_REGEX.search(pkg_name))

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
    
    def build_path_map() -> dict:
        """
        Read /var/lib/dpkg/info/<pkg>.list files directly — no subprocess.
        Returns {pkg_name: best_path} — empty string means no meaningful path found.

        Priority:
            1. Binary in BIN_DIRS          (/usr/bin/gparted, /usr/sbin/..., etc.)
            2. Shared library in LIB_DIRS  (/usr/lib/..., /lib/...) — .so files only
            3. Main executable in OPT_DIRS (/opt/vendor/app/binary)
            4. Empty string — no path stored (caller should omit the field)
        """
        BIN_DIRS = (
            "/usr/bin/", "/usr/sbin/", "/bin/", "/sbin/", "/usr/local/bin/", "/usr/local/sbin/",
        )
        LIB_DIRS = (
            "/usr/lib/", "/usr/lib64/", "/lib/", "/lib64/",
        )
        OPT_DIRS = (
            "/opt/",
        )

        # Paths we never want — skip immediately
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

        # Directories that are useless on their own (not files)
        USELESS = {
            ".", "/", "/.", "/usr", "/usr/share", "/usr/lib", "/usr/lib64",
            "/usr/sbin", "/usr/bin", "/bin", "/sbin", "/lib", "/lib64",
            "/usr/local", "/usr/local/bin", "/usr/local/sbin", "/opt",
        }

        DPKG_INFO_DIR = "/var/lib/dpkg/info"
        path_map = {}

        try:
            for fname in os.listdir(DPKG_INFO_DIR):
                if not fname.endswith(".list"):
                    continue

                pkg_name = fname[:-5].split(":")[0]
                best_bin = ""
                best_lib = ""
                best_opt = ""

                try:
                    with open(os.path.join(DPKG_INFO_DIR, fname), "r") as fh:
                        for line in fh:
                            path = line.strip()
                            if not path or path in USELESS:
                                continue
                            if any(path.startswith(s) for s in SKIP_PREFIXES):
                                continue

                            # Tier 1: actual binary
                            if not best_bin and any(path.startswith(b) for b in BIN_DIRS):
                                best_bin = path
                                break  # can't do better than this

                            # Tier 2: shared library (.so file — indicates the package's main artifact)
                            if not best_lib and any(path.startswith(l) for l in LIB_DIRS):
                                if ".so" in path:
                                    best_lib = path

                            # Tier 3: something inside /opt (vendor apps like Chrome)
                            if not best_opt and path.startswith("/opt/"):
                                # Only take actual files, not just /opt/google or /opt/google/chrome
                                if "." in os.path.basename(path) or os.path.basename(path) == path.split("/")[-1]:
                                    best_opt = path

                except (OSError, PermissionError):
                    pass

                # Use the best tier found; store nothing if none found
                chosen = best_bin or best_lib or best_opt
                if chosen:
                    path_map[pkg_name] = chosen
                # No entry at all for packages with no meaningful path
                # (caller should treat missing key as "no path")

        except Exception as e:
            logging.error("build_path_map error: %s", repr(e))

        return path_map

    def build_desktop_path_map() -> dict:
        """Parse Exec= from .desktop files — great for GUI apps."""
        result = {}
        for fpath in glob.glob("/usr/share/applications/*.desktop"):
            cp = configparser.RawConfigParser(strict=False, interpolation=None)
            cp.read(fpath)
            try:
                exec_val = cp.get("Desktop Entry", "Exec")
                # Strip args like %u %f %F
                binary = exec_val.split()[0].strip()
                # Strip env wrappers like env VAR=x /usr/bin/foo
                if binary == "env":
                    binary = exec_val.split()[2].strip()
                name = cp.get("Desktop Entry", "Name", fallback=None)
                if name and binary.startswith("/"):
                    result[name.lower()] = binary
            except (configparser.NoSectionError, configparser.NoOptionError, IndexError):
                pass
        return result

    def build_snap_path_map() -> dict:
        """Read snap package info from snapd's state file — no subprocess."""
        import json
        result = {}
        try:
            with open("/var/lib/snapd/state.json") as f:
                state = json.load(f)
            for snap_id, snap_data in state.get("data", {}).get("snaps", {}).items():
                name = snap_data.get("name")
                if name:
                    # Snap wrappers always live at /snap/bin/<name>
                    wrapper = f"/snap/bin/{name}"
                    result[name] = wrapper
        except (OSError, KeyError, json.JSONDecodeError):
            pass
        return result

    def build_combined_path_map() -> dict:
        dpkg = build_path_map()  # your existing function (fixed)
        desktop = build_desktop_path_map()
        snap = build_snap_path_map()

        # Start with dpkg, then let .desktop override where dpkg gave a lib path
        combined = dict(dpkg)
        for pkg_name, path in dpkg.items():
            # If dpkg gave a lib path (.so), check if desktop has a better answer
            if path and ".so" in path:
                desktop_hit = desktop.get(pkg_name.lower())
                if desktop_hit:
                    combined[pkg_name] = desktop_hit

        # Add snap packages that weren't in dpkg at all
        for name, path in snap.items():
            if name not in combined:
                combined[name] = path

        return combined

    def get_package_date(pkg_name: str, fallback: str) -> str:
        try:
            doc_path = f"/usr/share/doc/{pkg_name}"
            if os.path.exists(doc_path):
                ts = os.stat(doc_path).st_mtime  # pure syscall — no subprocess
                return datetime.fromtimestamp(int(ts)).strftime("%d-%m-%Y %H:%M:%S")
        except Exception:
            pass
        return fallback

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
    path_map = build_combined_path_map()


    # ─────────────────────────────────────────────────────────────────────────
    # STEP 3: Process each package — now pure Python, no subprocesses
    # ─────────────────────────────────────────────────────────────────────────
    for pkg_name, version, maintainer in raw_packages:
        try:
            version_clean = extract_real_version(version)
            path = path_map.get(pkg_name) or path_map.get(pkg_name.lower(), "")  # O(1) dict lookup

            date = get_package_date(pkg_name, os_installation_date)  # os.stat only

            signed = True
            signed_by = extract_maintainer_org(maintainer)
            authority = "Ubuntu APT Repository"
            clean_name = clean_package_name(pkg_name)
            normalized_name = FAMILY_NAME_OVERRIDE.get(clean_name, clean_name)
            lookup = normalized_name.lower()
            if lookup in DISPLAY_NAME_OVERRIDE:
                normalized_name = DISPLAY_NAME_OVERRIDE[lookup]

            lookup = normalized_name.lower()
            vendor = extract_maintainer_org(maintainer)
            if lookup in VENDOR_OVERRIDE:
                vendor = VENDOR_OVERRIDE[lookup]

            app_obj = {
                "name": normalized_name,
                "version": version_clean,
                "vendor": vendor,
                "date": date,
                "path": path,
                "signed": signed,
                "signedBy": signed_by,
                "authority": authority,
            }
            applications_versions.append(app_obj)

        except Exception as e:
            logging.warning("APT process error for %s: %s", pkg_name, e)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 4: Snap packages — unchanged, but use fallback path helper
    # ─────────────────────────────────────────────────────────────────────────
    try:
        snap_result = subprocess.run(
            ["snap", "list"],
            capture_output=True, text=True,
            timeout=TIMEOUT_SUBPROCESS
        )
        if snap_result.returncode == 0:
            for line in snap_result.stdout.strip().split("\n")[1:]:
                try:
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    pkg_name = parts[0]
                    version = parts[1]
                    publisher = parts[4] if len(parts) >= 5 else "Snap Store"

                    if should_skip(pkg_name):
                        continue

                    date = os_installation_date
                    path = f"/snap/{pkg_name}/current"
                    signed = True
                    signed_by = extract_maintainer_org(publisher)
                    authority = "Snap Store"

                    clean_name = clean_package_name(pkg_name)
                    normalized_name = FAMILY_NAME_OVERRIDE.get(clean_name, clean_name)
                    lookup = normalized_name.lower()
                    if lookup in DISPLAY_NAME_OVERRIDE:
                        normalized_name = DISPLAY_NAME_OVERRIDE[lookup]

                    lookup = normalized_name.lower()
                    vendor = extract_maintainer_org(publisher)
                    if lookup in VENDOR_OVERRIDE:
                        vendor = VENDOR_OVERRIDE[lookup]

                    app_obj = {
                        "name": normalized_name,
                        "version": version,
                        "vendor": vendor,
                        "date": date,
                        "path": path,
                        "signed": signed,
                        "signedBy": signed_by,
                        "authority": authority,
                    }
                    applications_versions.append(app_obj)

                except Exception as e:
                    logging.warning("Snap parse error for line %s: %s", line, e)

    except FileNotFoundError:
        logging.info("snap not installed — skipping")
    except Exception as e:
        logging.error("Snap fetch error: %s", repr(e))

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 5: Deduplication — unchanged
    # ─────────────────────────────────────────────────────────────────────────
    seen = {}
    for app in applications_versions:
        key = re.sub(r'[^a-z0-9]+', '', app["name"].lower())
        source_priority = 0 if app.get("authority") == "Ubuntu APT Repository" else 1
        if key not in seen:
            app["_priority"] = source_priority
            seen[key] = app
        else:
            if source_priority < seen[key]["_priority"]:
                app["_priority"] = source_priority
                seen[key] = app

    deduplicated = list(seen.values())
    for app in deduplicated:
        app.pop("_priority", None)

    # ─────────────────────────────────────────────────────────────────────────
    # STEP 6: Filter & sort — unchanged
    # ─────────────────────────────────────────────────────────────────────────
    return deduplicated

data = get_application_patch_info(datetime.now().strftime("%Y-%m-%d"))
# print("Total Application Found :",len(data))
# print(json.dumps(data, indent=2))
# Save JSON (overwrites existing file)
with open("installed_applications.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("JSON saved to installed_applications.json")
