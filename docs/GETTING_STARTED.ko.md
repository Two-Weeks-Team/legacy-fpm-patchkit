# 한글 시작 가이드

대상은 Linux 빌드와 기존 FPM 운영을 할 수 있는 관리자입니다. 새 서버에는 지원 중인 PHP와 OS를 우선 사용하세요.

## 1. 공개 도구 확인

제어용 컴퓨터에 Python 3.10 이상·Git·`patch`를 준비합니다. macOS 또는 Linux에서 다음을 실행합니다.

```sh
git clone https://github.com/Two-Weeks-Team/legacy-fpm-patchkit.git
cd legacy-fpm-patchkit
python3 -m patchkit verify
python3 -m unittest discover -v
```

`INPUTS_VERIFIED`와 단위 테스트 통과를 확인합니다. 아직 PHP를 실행하거나 설치한 것은 아닙니다.

## 2. 원본 재구성

```sh
python3 -m patchkit fetch
python3 -m patchkit prepare
```

공식 파일 약 12 MB를 받아 해시를 검사하고, Ubuntu 패치 84개와 이 프로젝트 패치를 적용합니다. 변경 파일 46개와 전체 소스가 일치하면 `SOURCE_VERIFIED`가 나옵니다. 결과는 `.work/source`와 그 옆의 준비 기록·로그입니다. 기존 디렉터리는 덮어쓰지 않습니다.

다시 독립 실행할 때는 `python3 -m patchkit prepare --output .work/source-second`처럼 새 경로를 지정하세요. 불일치가 발생하면 원인을 조사하고, 통과시키려고 기대 해시를 바꾸지 마세요.

## 3. 격리 Linux에서 빌드

운영 계정·비밀정보·운영 네트워크 접근이 없는 별도 Linux VM 또는 전용 CI runner를 사용합니다. macOS에서 소스를 준비했다면 리포와 준비한 소스를 해당 Linux로 옮깁니다.

[빌드 가이드](BUILDING.md)의 의존성을 갖춘 뒤 실행합니다.

```sh
bash scripts/build.sh .work/source .work/build portable
```

`portable`은 격리 기능 시험용입니다. Ubuntu 16.04 x86-64 프로필은 해당 OS에서 `xenial-amd64`로 지정합니다. 빌드 입력은 보존하고 별도 복사본에서 컴파일합니다. 시스템 경로에 설치하지 않습니다.

## 4. 실제 FPM 검사와 복구 연습

```sh
python3 scripts/native-check.py \
  --fpm .work/build/php-fpm --cli .work/build/php \
  --output .work/native-result.json
python3 -m patchkit inspect \
  --binary .work/build/php-fpm --build-record .work/build/build.json
python3 -m patchkit rehearse \
  --candidate .work/build/php-fpm --output .work/recovery-drill
```

첫 명령은 임시 설정·Unix 소켓으로 시험용 FPM을 실행해 세션·직렬화 설정·작은 업로드·동일 worker 연속 요청을 검사하고 자신이 실행한 FPM을 종료합니다. Python `-O` 옵션은 사용하지 마세요. `inspect`는 바이너리를 실행하지 않고 읽기만 하며, `rehearse`는 새 디렉터리에 만든 가짜 원본으로 백업·교체·복구를 연습합니다.

`BENIGN_RUNTIME_PASS`는 해당 정상 기능의 실제 검사 결과입니다. 모든 취약점·확장 모듈·사이트 호환성이 검증됐다는 뜻이 아닙니다. 실제 전환 전 [지원 범위](../SUPPORT.md), [동작 변화](BEHAVIOR_CHANGES.md), [적용·복구](INSTALLATION.md)를 확인하세요.
