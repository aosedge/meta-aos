#!/usr/bin/env python3
""" Calls bitbake command line """

import os


def call_bitbake(work_dir, yocto_dir, build_dir, target, bbake_conf, do_clean=False):
    """Calls bitbake."""
    print(f"Bitbake target: {target}...\n")

    # Create config file

    conf_file = os.path.abspath(os.path.join(work_dir, f"{target}.conf"))

    create_bbake_conf(conf_file, bbake_conf)

    cmd = [f"cd {yocto_dir}", f". ./poky/oe-init-build-env {build_dir}"]

    if do_clean:
        cmd.append(f"bitbake {target} -c cleanall")

    cmd.append(f"bitbake {target} --postread {conf_file}")

    line = " && ".join(c for c in cmd)

    ret = os.system(f'bash -c "{line}"')

    return ret >> 8


def create_bbake_conf(conf_file, bbake_conf):
    """Creates yocto conf file."""

    with open(conf_file, "w+", encoding="utf8") as file:
        for var in bbake_conf:
            file.write(f'{var[0]} = "{var[1]}"\n')
