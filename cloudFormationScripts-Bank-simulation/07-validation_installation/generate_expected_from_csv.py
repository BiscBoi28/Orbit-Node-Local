#!/usr/bin/env python3
"""
Read ORBIT_simulated_bank.csv and generate expected_installation.yml for validation.
Maps CSV rows to: OS family/distribution/version, packages list, and known systemd/service names.
"""
import csv
import os
import sys

def norm_os(csv_os):
    csv_os = (csv_os or "").strip().lower()
    if "rhel" in csv_os or "red hat" in csv_os:
        return "RedHat", "8"
    if "ubuntu" in csv_os:
        if "22" in csv_os:
            return "Ubuntu", "22"
        return "Ubuntu", "22"
    if "windows" in csv_os:
        if "2022" in csv_os:
            return "Windows", "2022"
        return "Windows", "2022"
    return None, None

def packages_list(csv_packages):
    if not csv_packages:
        return []
    return [p.strip() for p in csv_packages.replace('"', '').split(",") if p.strip()]

# Hostname -> list of systemd (Linux) or Windows service names to validate stop/start.
EXPECTED_SERVICES = {
    "corebank-db-01": ["postgresql-15", "tomcat"],
    "corebank-web-01": ["nginx", "php8.1-fpm"],
    "corp-ad-01": [],
}

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root = os.environ.get("ROOT_DIR", os.path.dirname(script_dir))
    csv_path = os.environ.get("CSV_FILE", "")
    if not csv_path:
        csv_path = os.path.join(root, "ORBIT_simulated_bank.csv")
    if not os.path.isfile(csv_path):
        sys.stderr.write("CSV not found: %s\n" % csv_path)
        sys.exit(1)

    out_path = os.environ.get("OUT_FILE", "")
    if not out_path:
        out_path = os.path.join(script_dir, "expected_installation.yml")

    rows = []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            hostname = (r.get("Hostname") or "").strip()
            if not hostname:
                continue
            os_raw = (r.get("Operating_System") or "").strip()
            dist, ver = norm_os(os_raw)
            pkgs = packages_list((r.get("OpenSource_Software_To_Install") or "").strip())
            services = EXPECTED_SERVICES.get(hostname, [])
            rows.append((hostname, dist, ver, pkgs, services))

    with open(out_path, "w") as w:
        w.write("---\n# Generated from %s. Do not edit by hand.\nexpected_hosts:\n" % csv_path)
        for hostname, dist, ver, pkgs, services in rows:
            w.write("  %s:\n" % hostname)
            w.write("    os_family: %s\n" % ("RedHat" if dist == "RedHat" else "Debian" if dist == "Ubuntu" else "Windows"))
            w.write("    os_distribution: %s\n" % (dist or ""))
            w.write("    os_major_version: '%s'\n" % (ver or ""))
            w.write("    packages: %s\n" % pkgs)
            w.write("    services: %s\n" % services)
    print(out_path)

if __name__ == "__main__":
    main()
