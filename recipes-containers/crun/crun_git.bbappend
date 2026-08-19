EXTRA_OECONF:append = " --enable-shared"

# crun ships its own top-level GNUmakefile that only forwards to the
# real build once ./autogen.sh && ./configure have run. OE's
# autotools_preconfigure runs "make clean" before that point and picks
# up this GNUmakefile (make prefers it over Makefile), hitting its
# "abort-due-to-no-makefile" guard target and failing do_configure.
CLEANBROKEN = "1"
