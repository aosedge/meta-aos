# It is required to compile on dunfell

do_compile:prepend() {
	export GO111MODULE=off
}
