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

BRANCH = "develop"
SRCREV = "6993b129b85ff5b7d51521b05f2acaed3f5b5f23"

SRC_URI = "git://github.com/aosedge/refpolicy.git;branch=${BRANCH};protocol=https;name=refpolicy;destsuffix=refpolicy"

SRC_URI += " \
    file://customizable_types \
    file://setrans-mls.conf \
    file://setrans-mcs.conf \
"

POLICY_NAME = "aos"
POLICY_TYPE = "mcs"
POLICY_MLS_SENS = "0"
