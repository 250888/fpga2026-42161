"""FE-16 布线管线一键执行（顺序敏感，勿手动跳步）。

    gen_frontend16  → 无走线 pcb + sch + BOM（会覆盖旧 pcb！）
    gen_dsn         → Specctra DSN
    freerouting     → SES（0 未布通 0 违例才继续）
    route_ses       → 走线回填 pcb（最终产物）
    pytest          → 12 项机检

用法：uv run python run_pipeline.py [--skip-route]
  --skip-route  跳过 freerouting（复用已有 xunji_fe16.ses）
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
JAVA = Path(r"C:\xjbuild\jre25\jdk-25.0.4.1+1-jre\bin\java.exe")
JAR = Path(r"C:\xjbuild\freerouting-2.5.0.jar")
SES = HERE / "xunji_fe16.ses"


def run(*cmd: str) -> None:
    print(f"$ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=HERE, check=True)


def main() -> None:
    py = sys.executable
    run(py, "gen_frontend16.py")
    run(py, "gen_dsn.py")
    if "--skip-route" in sys.argv:
        if not SES.exists():
            sys.exit("--skip-route 但无既有 SES")
        print(f"复用已有 SES ({SES.stat().st_size} bytes)")
    else:
        if not (JAVA.exists() and JAR.exists()):
            sys.exit(f"缺 freerouting 运行时: {JAVA} / {JAR}")
        # JAR 版而非 native CLI：CLI 2.5.0 有 BoardHistory 序列化
        # native-image bug（freerouting#957），JAR 在 JVM 上正常。
        log = Path(r"C:\xjbuild\freerouting_jar.log")
        with log.open("w", encoding="utf-8") as f:
            r = subprocess.run(
                [str(JAVA), "-jar", str(JAR), "-de", "xunji_fe16.dsn",
                 "-do", "xunji_fe16.ses", "-mp", "100"],
                cwd=HERE, stdin=subprocess.DEVNULL, stdout=f,
                stderr=subprocess.STDOUT)
        tail = log.read_text(encoding="utf-8", errors="replace")[-2000:]
        if r.returncode != 0 or not SES.exists():
            sys.exit(f"freerouting 失败 (rc={r.returncode}):\n{tail}")
        if "0 unrouted and 0 violations" not in tail:
            sys.exit(f"布线未满分，人工检查:\n{tail}")
        print("freerouting: 0 unrouted, 0 violations")
    run(py, "route_ses.py")
    run(py, "-m", "pytest", str(HERE.parents[1] / "tests" / "test_frontend_pcb.py"),
        "-q")


if __name__ == "__main__":
    main()
