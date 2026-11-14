#!/usr/bin/env bash
# Build only. Never make install, replace a system file, or control a service.
set -euo pipefail
if [ "$#" -ne 3 ]; then
  echo 'Usage: bash scripts/build.sh PREPARED_SOURCE NEW_OUTPUT portable|xenial-amd64' >&2
  exit 2
fi
kit=$(cd "$(dirname "$0")/.." && pwd)
source_dir=$(cd "$1" && pwd)
output=$2
profile=$3
[ "$(uname -s)" = Linux ] || { echo 'Linux build environment required' >&2; exit 2; }
[ ! -e "$output" ] && [ ! -L "$output" ] || { echo 'Output must be a new path' >&2; exit 2; }
case "$profile" in
  portable) ;;
  xenial-amd64)
    [ "$(uname -m)" = x86_64 ] || exit 2
    grep -qx 'VERSION_ID="16.04"' /etc/os-release || { echo 'xenial-amd64 requires Ubuntu 16.04' >&2; exit 2; }
    ;;
  *) echo 'Unknown build profile' >&2; exit 2 ;;
esac
python3 "$kit/scripts/check-build-source.py" "$source_dir"
mkdir -p "$output"
output=$(cd "$output" && pwd)
# The prepared input remains immutable. All generators/buildconf run on this copy.
cp -R "$source_dir" "$output/source"
src="$output/source"
export PHP_INI_SCAN_DIR=
if command -v dpkg-architecture >/dev/null 2>&1; then
  export DEB_HOST_MULTIARCH
  DEB_HOST_MULTIARCH=$(dpkg-architecture -qDEB_HOST_MULTIARCH)
fi
export CFLAGS='-O2 -g -fPIE -fstack-protector-strong -Wformat -Werror=format-security -fno-strict-aliasing -fsigned-char'
export CPPFLAGS='-D_FORTIFY_SOURCE=2'
export LDFLAGS='-Wl,-Bsymbolic-functions -fPIE -pie -Wl,-z,relro -Wl,-z,now -Wl,--as-needed'
{
  uname -sm
  cc --version | head -1
  autoconf --version | head -1
  re2c --version
} > "$output/toolchain.txt"
cd "$src"
# Checked-in Zend VM generated headers are frozen with the patch. re2c-generated
# C files must be rebuilt from the patched .re inputs.
re2c --no-generation-date -b -o ext/standard/var_unserializer.c ext/standard/var_unserializer.re
re2c --no-generation-date -b -o ext/standard/url_scanner_ex.c ext/standard/url_scanner_ex.re
re2c -d -b -o ext/date/lib/parse_date.c ext/date/lib/parse_date.re
re2c -d -b -o ext/date/lib/parse_iso_intervals.c ext/date/lib/parse_iso_intervals.re
[ ! -f ext/ext_skel ] || mv ext/ext_skel ext/ext_skel.in
./buildconf --force > "$output/buildconf.log" 2>&1
mkdir "$output/objects"
cd "$output/objects"
args=(--prefix=/opt/legacy-fpm-patchkit --enable-fpm --enable-cli --disable-cgi
      --disable-phpdbg --disable-all --disable-debug --disable-rpath --disable-static
      --with-pic --without-pear --enable-filter --enable-hash --enable-session
      --with-config-file-path=/etc/php/7.0/fpm --with-config-file-scan-dir=/etc/php/7.0/fpm/conf.d
      --with-fpm-user=www-data --with-fpm-group=www-data)
if [ "$profile" = xenial-amd64 ]; then
  args+=(--with-openssl=yes --with-pcre-regex=/usr --with-mhash=/usr --enable-libxml
         --with-system-tzdata --with-zlib=/usr --with-zlib-dir=/usr --enable-dtrace
         --with-libevent-dir=/usr --with-fpm-systemd --build=x86_64-linux-gnu --host=x86_64-linux-gnu)
else
  args+=(--without-libxml --enable-json)
fi
printf '%s\n' "${args[@]}" > "$output/configure-arguments.txt"
"$src/configure" "${args[@]}" > "$output/configure.log" 2>&1
make -j"${JOBS:-2}" EXTRA_CFLAGS='-Werror=implicit-function-declaration -Werror=int-conversion' > "$output/make.log" 2>&1
cp sapi/cli/php "$output/php"
cp sapi/fpm/php-fpm "$output/php-fpm"
readelf -h "$output/php-fpm" > "$output/elf-header.txt"
readelf -d "$output/php-fpm" > "$output/elf-dynamic.txt"
ldd "$output/php-fpm" > "$output/libraries.txt"
python3 "$kit/scripts/build-record.py" "$output" "$profile"
