"""Korean diagnostics at the command-line boundary. Preserve the original tool detail."""
import argparse
import errno
import os
import re
import subprocess
import sys


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        fields = re.fullmatch(r"argument (.+?): invalid choice: (.+?) \(choose from (.+)\)", message)
        if any("가" <= c <= "힣" for c in message):
            detail = message
        elif fields:
            detail = f"{fields[1]}에 지원하지 않는 값 {fields[2]}을 지정했습니다. 선택 가능한 값은 {fields[3]}입니다."
        elif message.startswith("the following arguments are required: "):
            detail = "필수 인수가 누락됐습니다: " + message.split(": ", 1)[1]
        elif message.startswith("unrecognized arguments: "):
            detail = "알 수 없는 인수입니다: " + message.split(": ", 1)[1]
        elif message.endswith(": expected one argument"):
            detail = message.split(": ", 1)[0].removeprefix("argument ") + "에 값을 지정하세요."
        else:
            detail = "명령 또는 옵션의 값이 올바르지 않습니다. --help로 사용법을 확인하세요."
        self.exit(2, f"오류: {detail}\n")


def describe(error):
    if isinstance(error, KeyboardInterrupt):
        return "사용자가 실험을 중단했습니다."
    if isinstance(error, OSError):
        reason = {
            errno.ENOENT: "필요한 파일이나 실행 프로그램을 찾을 수 없습니다",
            errno.ENOSPC: "파일을 쓸 저장 공간이 부족합니다",
            errno.EDQUOT: "저장 공간 할당량을 모두 사용했습니다",
            errno.EACCES: "접근 권한이 없습니다",
            errno.EPERM: "요청한 작업에 필요한 권한이 없습니다",
            errno.EEXIST: "이미 존재하는 경로입니다. 새 결과 이름을 지정하세요",
            errno.EROFS: "읽기 전용 파일시스템입니다",
            errno.ENOEXEC: "이 장비에서 실행할 수 없는 형식입니다",
            errno.ENOMEM: "실행 중 메모리가 부족해졌습니다",
        }.get(error.errno)
        if reason:
            return reason + (f" ({os.fsdecode(error.filename)})" if error.filename else "")
    if isinstance(error, subprocess.TimeoutExpired):
        return f"실행 시간이 {error.timeout}초를 초과했습니다 ({error.cmd})."
    if isinstance(error, subprocess.CalledProcessError):
        return f"하위 명령이 종료 코드 {error.returncode}로 실패했습니다 ({error.cmd})."
    detail = str(error)
    if any("가" <= c <= "힣" for c in detail):
        return detail
    return f"실험을 완료할 수 없습니다. 다음 진단과 해당 실행 로그를 확인하세요.\n{detail}"


def main_entry(main):
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print("오류: " + describe(error), file=sys.stderr, flush=True)
        raise SystemExit(130 if isinstance(error, KeyboardInterrupt) else 1) from None
