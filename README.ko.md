# Legacy FPM Patchkit

**PHP 7.0 FPM을 즉시 업그레이드하기 어려운 운영자를 위한 소스·빌드·검증 도구입니다.**

원본을 재구성하고, 패치를 확인하고, 격리 환경에서 빌드한 뒤 자신의 환경에서 검증합니다.

[English](README.md) · [시작하기](docs/GETTING_STARTED.ko.md) · [지원 범위](SUPPORT.md) · [검증 기록](docs/VERIFICATION.md) · [전체 문서](docs/README.md)

소스 릴리스에는 SHA-256 체크섬과 GitHub 출처 증명이 포함됩니다. [다운로드 검증 방법](docs/RELEASE_NOTES.md)을 확인하세요.

![원본 확인부터 적용 판단까지](docs/media/flow.svg)

> **지원이 종료된 런타임을 위한 소스 배포판입니다.** Ubuntu `7.0.33-0ubuntu0.16.04.16` 소스에 특정 보안 변경을 이식합니다. PHP 7.0 전체의 보안 지원을 복구하거나 모든 확장 모듈·사이트의 호환성을 보장하지 않습니다. 가능하면 공식 지원 중인 PHP로 이전하세요.

## 제공하는 것

- 공식 원본 파일 3개의 다운로드 주소·SHA-256, Ubuntu vendor 패치 84개를 적용하는 절차
- build007 누적 보안 패치와 변경 파일 46개의 전후 해시, 전체 소스 정합성 검사
- 비공개 경로에 의존하지 않는 Linux 빌드 프로필과 새 바이너리의 빌드 기록
- 실제 로컬 FPM을 이용한 세션·직렬화 설정·작은 파일 업로드·동일 worker 연속 요청 검사
- 바이너리를 실행하지 않는 ELF·해시 검사와 새 임시 디렉터리에서의 백업·교체·복구 연습
- 영문·한글 안내, 적용·복구 절차, 알려진 동작 변화와 검증 한계

## 시작하기

제어용 컴퓨터에는 Python **3.10 이상**, Git, `patch`가 필요합니다. 소스 준비는 macOS·Linux에서, 컴파일은 별도 Linux 환경에서 진행합니다. Python 패키지 설치는 필요 없습니다.

```sh
git clone https://github.com/Two-Weeks-Team/legacy-fpm-patchkit.git
cd legacy-fpm-patchkit
python3 -m patchkit verify
python3 -m unittest discover -v
python3 -m patchkit fetch
python3 -m patchkit prepare
```

이 명령들은 운영 서버에 접속하거나 서비스를 변경하지 않습니다. `prepare`는 새로운 디렉터리에만 소스를 만들고 기존 작업물을 덮어쓰지 않습니다. 다음 단계는 [한글 시작 가이드](docs/GETTING_STARTED.ko.md)를 따르세요.

## 적용 범위

대상은 CVE-2026-109618·CVE-2026-109619와 관련된 upstream 상태 손상·메모리 부족 처리 변경의 PHP 7.0 이식입니다. 런타임에서 세션 직렬화 방식을 다른 것으로 바꾸는 동작은 의도적으로 거부합니다. 최초 설정에서 직렬화 방식을 선택하거나 같은 값을 다시 지정하는 동작은 유지합니다.

`portable` 빌드는 격리 회귀 시험용입니다. `xenial-amd64`는 Ubuntu 16.04 x86-64 프로필입니다. 버전이나 OS 이름이 같아도 바이너리·라이브러리·확장 모듈·애플리케이션 검증을 생략할 수 없습니다. [지원 범위](SUPPORT.md), [동작 변화](docs/BEHAVIOR_CHANGES.md)를 먼저 확인하세요.

빌드 도구는 시스템 설치·서비스 재시작·컨테이너 제어를 하지 않습니다. 로컬 시험 도구가 띄운 FPM만 시험 후 종료합니다. 실제 서비스 전환은 [적용·복구 절차](docs/INSTALLATION.md)에 따라 운영자가 별도로 수행합니다.

## 공개 자료와 검증

실제 소스 준비, 새 빌드, 정상 기능 검사와 과거 보안 시험은 각각 구분해 기록합니다. 모의 테스트를 운영 검증 통과로 표시하지 않습니다. 운영 로그·접속 정보·승인 기록·사이트 코드는 포함하지 않습니다.

기여 방법은 [CONTRIBUTING.md](CONTRIBUTING.md), 비공개 보안 제보는 [SECURITY.md](SECURITY.md)를 참고하세요. 새 도구의 MIT 라이선스와 PHP 유래 패치의 라이선스는 구분됩니다. [제3자 고지](THIRD_PARTY_NOTICES.md)를 확인하세요.

This product includes PHP software, freely available from <http://www.php.net/software/>.

This product includes the Zend Engine, freely available at <http://www.zend.com>.
