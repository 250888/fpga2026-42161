# 子进程统一出口：UTF-8 replace 防 GBK 崩溃（设计 I3）、超时、退出码透传
import subprocess
from dataclasses import dataclass

@dataclass
class RunResult:
    code: int
    out: str
    timed_out: bool = False

def run_tool(cmd: list[str], *, timeout: int, cwd: str | None = None) -> RunResult:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return RunResult(code=p.returncode, out=p.stdout + p.stderr)
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        err = e.stderr or ""
        if isinstance(err, bytes):
            err = err.decode("utf-8", errors="replace")
        return RunResult(code=124, out=out + err + f"\n[TIMEOUT after {timeout}s]", timed_out=True)
    except FileNotFoundError:
        return RunResult(code=127, out=f"工具不存在: {cmd[0]}")
