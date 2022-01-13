DESCRIPTION = "AOS Update Manager"

GO_IMPORT = "aos_updatemanager"

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://src/${GO_IMPORT}/LICENSE;md5=3b83ef96387f14655fc854ddc3c6bd57"

BRANCH = "main"
SRCREV = "b93ee541821c34aed7993b76a79e5ac894531f4c"
SRC_URI = "git://git@github.com/aoscloud/${GO_IMPORT}.git;branch=${BRANCH};protocol=ssh"

inherit go

AOS_UM_UPDATE_MODULES ??= ""

# SM crashes if dynamic link selected, disable dynamic link till the problem is solved
GO_LINKSHARED = ""

# embed version
GO_LDFLAGS += '-ldflags="-X main.GitSummary=`git --git-dir=${S}/src/${GO_IMPORT}/.git describe --tags --always` ${GO_RPATH} ${GO_LINKMODE} -extldflags '${GO_EXTLDFLAGS}'"'

# this flag is requied when GO_LINKSHARED is enabled
# LDFLAGS += "-lpthread"

do_prepare_modules() {
    if [ -z "${AOS_UM_UPDATE_MODULES}" ]; then
        exit 0
    fi

    file="${S}/src/${GO_IMPORT}/updatemodules/modules.go"

    echo 'package updatemodules' > ${file}
    echo 'import (' >> ${file}

    for module in ${AOS_UM_UPDATE_MODULES}; do
        echo "\t_ \"github.com/aoscloud/aos_updatemanager/${module}\"" >> ${file}
    done

    echo ')' >> ${file}
}

RDEPENDS_${PN}-dev += " bash make"
RDEPENDS_${PN}-staticdev += " bash make"

addtask prepare_modules after do_unpack before do_compile