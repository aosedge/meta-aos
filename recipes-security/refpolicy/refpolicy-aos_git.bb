SUMMARY = "SELinux Aos policy based on targeted policy"
DESCRIPTION = "\
This is the Aos modification for targeted variant of the \
SELinux reference policy. Most service domains are locked \
down. Users and admins will login in with unconfined_t \
domain, so they have the same access to the system as if \
SELinux was not enabled. \
"

include recipes-security/refpolicy/refpolicy_common.inc

PV = "2_20220106+git${SRCPV}"

BRANCH = "master"
SRCREV = "4c5278e83cf9aec7108f7e86b910b43c4d58ecd0"

SRC_URI = "git://github.com/aosedge/refpolicy.git;branch=${BRANCH};protocol=https;name=refpolicy;destsuffix=refpolicy"

SRC_URI += " \
    file://customizable_types \
    file://setrans-mls.conf \
    file://setrans-mcs.conf \
"

POLICY_NAME = "aos"
POLICY_TYPE = "mcs"
POLICY_MLS_SENS = "0"
