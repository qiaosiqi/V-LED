# P9 最终回归、盲演与交付运行手册

> 状态：`P9_AUTHORIZED_IN_PROGRESS / TARGET_LINUX_AND_BLIND_DEMO_PENDING`
>
> P9 起点：`a6c517c143b9bcf525aa298371d07675c4e85679`。目标 Linux 只测试已普通
> fast-forward 推送到 `origin/integration-promote-try` 的 P9 准备提交。运行前把
> Codex 汇报的 40 位准备提交填入 `P9_COMMIT`，不得凭短哈希猜测。

## 1. 不可破坏项

1. 不执行 `git clean`、`git reset --hard`、force push 或 `--force-with-lease`。
2. 不修改或覆盖任何既有 `docs/evidence/` 原始证据；每次 P9 运行使用新目录。
3. Windows 权威工作区不得暂存或提交：
   - `docs/操作系统课程设计报告2026.doc` 的现有修改；
   - `.evidence-import-p1/`；
   - `docs/操作系统课程设计报告2026-草稿.docx`；
   - `docs/操作系统课程设计报告2026-草稿.pdf`。
4. P8 的 DOCX/PDF 只读，不重新导出、不覆盖：
   - `docs/操作系统课程设计报告2026-P8排版稿.docx`；
   - `docs/操作系统课程设计报告2026-P8排版稿.pdf`。
5. 任一步失败都保留本轮目录，不补写 PASS，不覆盖失败日志；修复后使用新运行编号。

## 2. 目标 Linux 同步与环境原始输出

在 Ubuntu 目标机的仓库根目录执行。第 2–6 节应使用同一个 Linux 终端，以保留
`P9_COMMIT`、`run_id`、`evidence` 和 `run_start`。`P9_COMMIT` 必须替换为 Codex
汇报的完整哈希：

```bash
cd "$HOME/siqi_ws/V-LED"
P9_COMMIT='<P9_PREPARATION_COMMIT_40_HEX>'

git status --short --branch
make -C driver clean
make -C tools clean
git fetch origin
git switch integration-promote-try
git pull --ff-only origin integration-promote-try

test "$(git rev-parse HEAD)" = "$P9_COMMIT"
test "$(git rev-parse origin/integration-promote-try)" = "$P9_COMMIT"
test -z "$(git status --porcelain --untracked-files=no)"
git status --short --branch
git rev-parse HEAD origin/integration-promote-try
```

预期：三个 `test` 均为退出码 0；`HEAD` 和远端跟踪引用均为同一完整哈希；允许继续
显示历史遗留的未跟踪 `get_env*.sh`，但不得出现已跟踪文件修改。若 `git pull
--ff-only` 拒绝或哈希不一致，立即停止并回传原始输出。

创建仓库外的新证据目录，并采集环境：

```bash
set -o pipefail
run_id="$(date +%Y%m%d-%H%M)-ubuntu-$(uname -r)-p9"
evidence="$HOME/vled-test-logs/$run_id"
mkdir -p "$evidence"
run_start=$(date --iso-8601=seconds)

{
    date --iso-8601=seconds
    pwd
    cat /etc/os-release
    uname -a
    gcc --version | head -n 1
    x86_64-linux-gnu-gcc-13 --version | head -n 1
    make --version | head -n 1
    ld --version | head -n 1
    python3 --version
    git --version
    git status --short --branch
    git rev-parse HEAD origin/integration-promote-try
    ls -ld "/lib/modules/$(uname -r)/build"
    test -f "/lib/modules/$(uname -r)/build/Makefile"
    timedatectl | sed -n '1,6p'
    systemd-detect-virt || true
    ip -br -4 addr
    ip route show default
} 2>&1 | tee "$evidence/00-environment.log"
env_rc=${PIPESTATUS[0]}
echo "00-environment exit code: $env_rc" | tee "$evidence/EXIT_CODES.txt"
test "$env_rc" -eq 0
```

预期：Ubuntu 24.04.4、`6.17.0-35-generic`、x86_64、GCC 13.3、匹配的内核
build 目录和明确 P9 提交均出现在原始日志中。实际环境若变化，不得照抄这里的旧值；
应保留实际输出并先评估是否仍是课程验收目标环境。

## 3. 干净构建与 P1–P5 最终回归

先卸载任何旧模块并确认节点消失：

```bash
if lsmod | awk '{print $1}' | grep -qx vled; then sudo rmmod vled; fi
lsmod | grep '^vled' || echo 'vled module: NOT LOADED'
test ! -e /dev/vled && echo '/dev/vled: absent'
```

执行加严的最终回归：500 次并发迭代、20 轮生命周期，以及统一入口已有的严格
构建、bridge 黑盒、P1 边界/多 FD、业务、并发、poll/wait queue 和内核日志检查。

```bash
VLED_ITERATIONS=500 VLED_LIFECYCLE_CYCLES=20 \
    ./tools/vled_verify.sh 2>&1 | tee "$evidence/01-final-verify.log"
verify_rc=${PIPESTATUS[0]}
echo "01-final-verify exit code: $verify_rc" | tee -a "$evidence/EXIT_CODES.txt"

lsmod | grep '^vled' || echo 'vled unloaded after verifier'
test ! -e /dev/vled && echo '/dev/vled removed after verifier'
if [[ $verify_rc -ne 0 ]]; then
    echo "P9 final verifier failed; preserve $evidence and stop" >&2
    exit "$verify_rc"
fi
```

通过条件：

- 驱动构建和 tools `-Werror` 构建均成功；
- bridge 黑盒、`vled_fd_probe`、`vled_verify.py`、`vled_poll_probe` 全部 PASS；
- 出现 `PASS lifecycle cycle 20`；
- 末行出现 `VLED P1-P5 verify: PASS (module will be unloaded by cleanup trap)`；
- `verify_rc=0`，模块已卸载且 `/dev/vled` 已消失；
- 本轮内核日志没有 warning/oops/BUG/lockdep/use-after-free/general protection fault。

## 4. 常见故障恢复彩排

以下两项是受控负面测试，不是正式 PASS 的替代品。它们验证 README 中的恢复说明，
并且不得编辑源码或既有证据。

### 4.1 已加载旧模块时拒绝替换

```bash
sudo insmod driver/vled.ko
loaded_rc=0
./tools/vled_verify.sh >"$evidence/02-loaded-module-rejection.log" 2>&1 \
    || loaded_rc=$?
cat "$evidence/02-loaded-module-rejection.log"
echo "02-loaded-module-rejection exit code: $loaded_rc" | tee -a "$evidence/EXIT_CODES.txt"
test "$loaded_rc" -eq 2
grep -F "Refusing to replace an already loaded vled module" \
    "$evidence/02-loaded-module-rejection.log"
sudo rmmod vled
test ! -e /dev/vled
```

预期：验收器退出码为 2，明确拒绝替换已加载模块；执行 `rmmod` 后节点消失。

### 4.2 演示设备路径错误及恢复

```bash
missing_rc=0
./tools/vled_demo.sh 192.168.57.1 /dev/vled-missing \
    >"$evidence/03-missing-device-rejection.log" 2>&1 \
    || missing_rc=$?
cat "$evidence/03-missing-device-rejection.log"
echo "03-missing-device-rejection exit code: $missing_rc" | tee -a "$evidence/EXIT_CODES.txt"
test "$missing_rc" -eq 1
grep -F "/dev/vled-missing is not a character device" \
    "$evidence/03-missing-device-rejection.log"

sudo insmod driver/vled.ko
sudo chmod 666 /dev/vled
test -c /dev/vled
```

预期：错误路径退出码为 1 且原因明确；按 README 加载模块并恢复正确路径后，
`test -c /dev/vled` 为 0。此时保留模块，供下一节盲演使用。

## 5. Windows 自动回归与非开发成员盲演

### 5.1 Windows 原始输出

在 Windows 权威工作区根目录开一个 PowerShell，执行：

```powershell
$runId = Get-Date -Format 'yyyyMMdd-HHmm'
$evidence = Join-Path $HOME "vled-test-logs\$runId-windows-p9"
New-Item -ItemType Directory -Force -Path $evidence | Out-Null

python --version 2>&1 | Tee-Object "$evidence\00-python.txt"
python -c "import tkinter; print('tkinter import: OK; TkVersion=', tkinter.TkVersion)" 2>&1 |
    Tee-Object -Append "$evidence\00-python.txt"

python -m unittest discover -s simulator/tests -v 2>&1 |
    Tee-Object "$evidence\01-simulator-unittest.log"
$testRc = $LASTEXITCODE
"01-simulator-unittest exit code: $testRc" |
    Tee-Object "$evidence\EXIT_CODES.txt"
if ($testRc -ne 0) { throw "Windows simulator regression failed: $testRc" }
```

预期：Python 3.12、Tkinter 可导入、17 项测试全部 `ok`，末尾 `OK`，退出码 0。
必须回传上述两个原始文本文件，不能只回传口述结论。

### 5.2 盲演规则

1. 盲演操作者必须是未参与实现的成员；只给他/她根 `README.md`、Windows IP
   `192.168.57.1` 和必要的 sudo 密码，不给本手册的通过条件或源码讲解。
2. 操作者按 README 在 Windows 启动：

   ```powershell
   python simulator/vled_sim.py 2>&1 |
       Tee-Object "$evidence\02-simulator-gui.log"
   $guiRc = $LASTEXITCODE
   "02-simulator-gui exit code: $guiRc" |
       Tee-Object -Append "$evidence\EXIT_CODES.txt"
   if ($guiRc -ne 0) { throw "Windows simulator GUI exited abnormally: $guiRc" }
   ```

3. 操作者按 README 在 Linux 运行：

   ```bash
   ./tools/vled_demo.sh 192.168.57.1 /dev/vled 2>&1 \
       | tee "$evidence/04-blind-demo.log"
   demo_rc=${PIPESTATUS[0]}
   echo "04-blind-demo exit code: $demo_rc" | tee -a "$evidence/EXIT_CODES.txt"
   test "$demo_rc" -eq 0
   ```

4. 观察者只记录，不在过程中提示下一条命令。完成后关闭 Windows 窗口，并记录 GUI
   进程退出码；保存未裁改的 Windows GUI PNG，画面须包含最终状态和 UDP 日志。
5. Linux 端完成后执行：

   ```bash
   ./tools/vled_cli read /dev/vled | tee "$evidence/05-final-state.json"
   sudo rmmod vled
   test ! -e /dev/vled
   sudo journalctl -k --since "$run_start" --no-pager 2>&1 \
       | tee "$evidence/06-final-kernel.log"
   grep -niE 'warning:|oops|BUG:|lockdep|use-after-free|general protection fault' \
       "$evidence/06-final-kernel.log" \
       && { echo 'forbidden kernel diagnostic found'; exit 1; } \
       || echo 'final kernel diagnostic check: PASS'
   ```

盲演通过条件：操作者无需开发者提示即可完成；Linux demo 依次显示 8 条 `>` 命令并
输出 `Demo complete; stopping bridge cleanly.`，退出码 0；Windows GUI 依次反映英文、
红色、80% 亮度、scroll、中文、青色、static 和清屏，version 随实际变化单调递增；
关闭窗口后进程退出；最终内核日志无禁止诊断。

## 6. 原始证据校验与回传

Linux 端生成清单和归档：

```bash
cd "$evidence"
sha256sum 00-environment.log 01-final-verify.log \
    02-loaded-module-rejection.log 03-missing-device-rejection.log \
    04-blind-demo.log 05-final-state.json 06-final-kernel.log \
    EXIT_CODES.txt > SHA256SUMS

cd "$HOME/vled-test-logs"
tar -czf "${run_id}.tar.gz" "$run_id"
sha256sum "${run_id}.tar.gz"
```

Windows 端生成清单：

```powershell
Get-ChildItem -LiteralPath $evidence -File |
    Get-FileHash -Algorithm SHA256 |
    Format-Table Hash,Path -AutoSize |
    Out-File -Encoding utf8 "$evidence\SHA256SUMS-WINDOWS.txt"
```

需要原样回传：

- Linux `${run_id}.tar.gz` 及终端打印的 tar.gz SHA-256；
- Windows `00-python.txt`、`01-simulator-unittest.log`、`02-simulator-gui.log`、
  `EXIT_CODES.txt`、`SHA256SUMS-WINDOWS.txt`；
- 未裁改 Windows GUI PNG；
- 盲演者姓名/角色以及“过程中是否获得开发者提示”的真实说明；
- 若任一步失败，失败目录和输出同样全部回传，不要只贴最后几行。

收到并复核这些原始材料前，P9 状态保持
`TARGET_LINUX_AND_BLIND_DEMO_PENDING`，不得写成 `PASS`。
